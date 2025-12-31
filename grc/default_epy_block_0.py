import numpy as np
from gnuradio import gr

class blk(gr.sync_block):
    def __init__(self, alpha=0.1):
        gr.sync_block.__init__(self, 
            name="Linear Bitrate Calc", 
            in_sig=[np.complex64], 
            out_sig=[np.float32])
        
        # 1. DEFINITIONS
        self.pwr_min = 0.3       # Baseline Power (Slider = 0)
        self.pwr_max = 1.3       # Max Power (Slider = 1)
        
        self.rate_max = 10000000.0 # 10 Mbps
        self.rate_min = 1000000.0  # 1 Mbps
        
        self.alpha = alpha       # Smoothing factor
        self.avg_power = 0.0     # State variable

    def work(self, input_items, output_items):
        if len(input_items[0]) == 0: return 0
            
        # 2. CALCULATE POWER
        inst_power = np.mean(np.abs(input_items[0])**2)
        
        # 3. SMOOTHING
        self.avg_power = (self.alpha * inst_power) + ((1 - self.alpha) * self.avg_power)
        
        # 4. MAPPING (The Fix)
        # First, find where we are in the power range (0.0 to 1.0)
        # This value increases QUADRATICALLY (slow start, fast finish)
        raw_factor = np.clip((self.avg_power - self.pwr_min) / (self.pwr_max - self.pwr_min), 0.0, 1.0)
        
        # We apply Square Root to "Linearize" it relative to the slider
        # If raw_factor is 0.25 (25% power), sqrt(0.25) = 0.5 (50% slider)
        linear_factor = np.sqrt(raw_factor)
        
        # 5. CALCULATE RATE
        # Now we use the linear_factor
        current_rate = self.rate_max - (linear_factor * (self.rate_max - self.rate_min))
        
        # 6. ROUNDING
        current_rate = round(current_rate / 100000) * 100000
        
        # DEBUG
        print(f"PWR: {self.avg_power:.2f} | FACTOR: {linear_factor:.2f} | RATE: {current_rate/1e6:.1f} Mbps", end='\r')

        output_items[0][:] = current_rate
        return len(output_items[0])