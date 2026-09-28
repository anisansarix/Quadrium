import numpy as np


class RollingHistory:
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.closes = np.zeros(max_size)
        self.count = 0
        
    def append(self, quote: float):
        if self.count < self.max_size:
            self.closes[self.count] = quote
            self.count += 1
        else:
            self.closes = np.roll(self.closes, -1)
            self.closes[-1] = quote
            
    def get_closes(self) -> np.ndarray:
        return self.closes[:self.count]
