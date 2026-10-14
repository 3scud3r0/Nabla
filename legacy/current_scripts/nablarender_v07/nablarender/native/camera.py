from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..core.math3d import look_at,perspective
@dataclass
class Camera:
    eye:tuple[float,float,float]=(52,-32,22); target:tuple[float,float,float]=(22,0,6); up:tuple[float,float,float]=(0,0,1); fovy_deg:float=42.; near:float=.1; far:float=600.
    def view_matrix(self): return look_at(np.array(self.eye),np.array(self.target),np.array(self.up))
    def projection_matrix(self,aspect): return perspective(self.fovy_deg,aspect,self.near,self.far)
