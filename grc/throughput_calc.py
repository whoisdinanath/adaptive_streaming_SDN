import numpy as np
from gnuradio import gr

class blk(gr.sync_block):
    def __init__(self, high_thresh=1.5, low_thresh=1.2, alpha=0.05):
        """
        Adaptive bitrate based on received signal power.
        
        Args:
            high_thresh: Power threshold to switch to low bitrate (1 Mbps)
            low_thresh: Power threshold to switch to high bitrate (5 Mbps)
            alpha: Smoothing factor (0-1, lower = smoother)
        
        Expected power ranges:
        - Clean signal (noise=0): ~1.0
        - Noisy signal (noise=0.5): ~1.5
        - Very noisy (noise=1.0): ~2.0
        """
        gr.sync_block.__init__(self, 
            name="Adaptive Bitrate Calculator", 
            in_sig=[np.complex64], 
            out_sig=[np.float32])
        
        self.high_thresh = high_thresh
        self.low_thresh = low_thresh
        self.alpha = alpha
        
        self.avg_power = 0.0
        self.last_rate = 5000000.0  # Start at 5 Mbps
        
        self.init_samples = 0
        self.init_period = 100  # Calibration period
        
        print(f"\n=== Adaptive Bitrate Block ===")
        print(f"High threshold: {high_thresh} (drop to 1 Mbps)")
        print(f"Low threshold: {low_thresh} (raise to 5 Mbps)")
        print(f"Hysteresis gap: {high_thresh - low_thresh}")
        print(f"Smoothing alpha: {alpha}\n")

    def work(self, input_items, output_items):
        if len(input_items[0]) == 0:
            return 0
        
        # Calculate instantaneous power
        inst_power = np.mean(np.abs(input_items[0])**2)
        
        # Initialize or smooth
        if self.init_samples < self.init_period:
            self.avg_power = inst_power
            self.init_samples += 1
        else:
            self.avg_power = (self.alpha * inst_power) + ((1 - self.alpha) * self.avg_power)
        
        # Apply hysteresis thresholds
        old_rate = self.last_rate
        
        if self.avg_power > self.high_thresh:
            # Channel degraded - reduce bitrate
            self.last_rate = 1000000.0  # 1 Mbps
            
        elif self.avg_power < self.low_thresh:
            # Channel improved - increase bitrate
            self.last_rate = 5000000.0  # 5 Mbps
        
        # If between thresholds, maintain current rate (hysteresis)
        
        # Log rate changes
        if old_rate != self.last_rate:
            rate_mbps = self.last_rate / 1e6
            direction = "↓" if self.last_rate < old_rate else "↑"
            print(f"\n{direction} RATE CHANGE: {rate_mbps:.1f} Mbps (Power: {self.avg_power:.3f})")
        
        # Periodic status (every ~1 second at 32kHz sample rate)
        if self.init_samples % 32000 == 0:
            rate_mbps = self.last_rate / 1e6
            status = "HIGH" if self.avg_power > self.high_thresh else "LOW" if self.avg_power < self.low_thresh else "MID"
            print(f"Power: {self.avg_power:.3f} [{status}] | Bitrate: {rate_mbps:.1f} Mbps", end='\r')
        
        self.init_samples += len(input_items[0])
        
        # Output constant rate for all samples
        output_items[0][:] = self.last_rate
        return len(output_items[0])