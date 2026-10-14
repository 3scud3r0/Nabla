from __future__ import annotations
from dataclasses import dataclass, field
from ..core.mesh import MeshInstance
@dataclass
class DirectionalLight: direction:tuple[float,float,float]=(-0.35,0.6,-0.72); color:tuple[float,float,float]=(1.0,.96,.88); intensity:float=4.8
@dataclass
class Environment: background_top:tuple[float,float,float]=(0.02,0.05,0.10); background_bottom:tuple[float,float,float]=(0.11,0.10,0.13); ambient:tuple[float,float,float]=(0.06,0.065,0.08)
@dataclass
class Scene:
    instances:list[MeshInstance]=field(default_factory=list); light:DirectionalLight=field(default_factory=DirectionalLight); environment:Environment=field(default_factory=Environment); metadata:dict=field(default_factory=dict)
    def add(self,inst:MeshInstance): self.instances.append(inst)
