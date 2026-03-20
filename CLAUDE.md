# Go2-X5 Loco-Manipulation 项目开发文档

## 项目概述

**目标：** 复现SAGE场景生成工作，将SAGE-10k数据集中的场景导入Isaac Sim，并在场景中放置Go2-X5四足机械臂机器人，为后续的VLA训练做准备。

**技术栈：**
- Isaac Sim: 4.5.0
- Isaac Lab: 2.1.0
- Python: 3.10.19
- PyTorch: 2.5.1+cu124
- GPU: NVIDIA GeForce RTX 4060 Ti (16GB)
- Conda环境: lab

**GitHub仓库：** https://github.com/54Tao/go2-loco-mani

**基于的代码仓库：**
- [SAGE](https://github.com/NVlabs/SAGE) - 场景生成框架
- [Go2-X5-lab](https://github.com/fan-ziqi/Go2-X5-lab) - 四足机械臂Isaac Lab扩展
- [SAGE-10k](https://huggingface.co/datasets/nvidia/SAGE-10k) - 场景数据集

---

## 目录结构

```
/home/tjz/go2_loco_mani/
├── Go2-X5-lab/              # Go2-X5机器人Isaac Lab扩展
│   ├── source/robot_lab/    # 机器人任务和配置
│   │   └── data/Robots/go2_x5/  # URDF和mesh文件
│   └── scripts/             # 训练和工具脚本
├── X5/                      # X5A机械臂原始文件
│   └── X5A/                 # X5A URDF + mesh（含夹爪）
├── sage/                    # SAGE场景生成框架
│   └── server/isaacsim/     # Isaac Sim MCP扩展
├── datasets/                # 数据集目录
│   └── sage-10k/            # SAGE-10k场景数据集
│       ├── scenes/          # 场景ZIP文件（526个）
│       ├── assets/          # 共享3D资产
│       └── kits/            # 导出工具
├── assets/                  # 生成的资产
│   ├── go2_x5.usd           # Go2-X5机器人USD（主文件）
│   └── configuration/       # USD配置文件
├── scripts/                 # 工具脚本
│   ├── visualize_scene_robot.py   # 可视化验证脚本
│   ├── integrate_robot_scene.py   # 场景机器人集成
│   └── batch_process_scenes.py    # 批量场景处理
├── configs/                 # 配置文件
│   ├── scene_robot_configs.yaml
│   └── batch_scene_configs.yaml
├── CLAUDE.md               # 本文档
└── README.md               # 项目说明
```

---

## 环境配置

### 1. Conda环境

```bash
conda activate lab
```

### 2. 已安装的关键包

| 包名 | 版本 | 用途 |
|------|------|------|
| isaaclab | 2.1.0 | Isaac Lab框架 |
| isaacsim | 4.5.0.0 | Isaac Sim仿真器 |
| robot_lab | 2.3.0 | Go2-X5扩展 |
| huggingface-hub | 0.36.0 | 数据集下载 |
| torch | 2.5.1+cu124 | 深度学习框架 |
| trimesh | 4.9.0 | PLY mesh加载 |

### 3. 安装Go2-X5扩展

```bash
cd /home/tjz/go2_loco_mani/Go2-X5-lab
conda run -n lab python -m pip install -e source/robot_lab
```

### 4. 环境变量（可选）

```bash
export SAGE_ROOT=/home/tjz/go2_loco_mani/sage
export GO2_LAB_ROOT=/home/tjz/go2_loco_mani/Go2-X5-lab
export SAGE_DATASET=/home/tjz/go2_loco_mani/datasets/sage-10k
```

---

## 实施进度总览

| 阶段 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 1 | SAGE-10k数据集获取 | ✅ 完成 | 526个场景 |
| 2 | Isaac Sim环境验证 | ✅ 完成 | headless模式初始化慢 |
| 3 | Go2-X5 URDF到USD转换 | ✅ 完成 | 第二次转换修复了机械臂问题 |
| 4 | 场景与机器人集成 | ✅ 完成 | PLY mesh加载+纹理 |
| 5 | 批量场景处理 | ✅ 完成 | 50个场景配置生成 |
| 6 | 文档编写 | ✅ 完成 | 持续更新中 |
| 7 | 替换X5A机械臂+夹爪 | ✅ 完成 | 6旋转+2棱柱关节，总DOF 20 |

---

## 详细实施记录

### 阶段1：SAGE-10k数据集获取

**任务：** 从HuggingFace下载SAGE-10k数据集

**操作命令：**
```bash
mkdir -p /home/tjz/go2_loco_mani/datasets/sage-10k
cd /home/tjz/go2_loco_mani/datasets/sage-10k
conda run -n lab huggingface-cli download nvidia/SAGE-10k --repo-type dataset --local-dir ./ --max-workers 4
```

**结果：**
- ✅ 成功下载526个场景ZIP文件
- 每个场景约50-100MB
- 总数据量约35GB+

**数据集结构分析：**

每个场景ZIP解压后的结构：
```
20251213_070212_layout_deedb66c/
├── layout_deedb66c.json    # 场景布局JSON（核心文件）
├── objects/                # PLY格式的3D物体 + 纹理PNG
│   ├── 04449a19.ply
│   ├── 04449a19_texture.png
│   └── ...
├── materials/              # 房间材质
│   ├── room_xxx_wall.png   # 墙面纹理
│   ├── room_xxx_floor.png  # 地板纹理
│   └── Door_3_texture.png  # 门纹理
└── preview/                # 预览图
    └── preview_*.png
```

**场景JSON格式关键字段：**
- `rooms[].room_type` - 房间类型（如bedroom, kitchen, living room）
- `rooms[].dimensions` - 房间尺寸（width, length, height）
- `rooms[].walls[]` - 墙体定义（start_point, end_point, height, thickness）
- `rooms[].objects[]` - 物体列表（position, rotation, dimensions, source_id）
- `rooms[].objects[].source_id` - 对应objects/目录下的PLY文件名

**场景统计（前50个场景）：**
- 房间类型：26种
- Top 5：master bedroom(7), living room(5), kitchen(4), warehouse(4), bathroom(3)

---

### 阶段2：Isaac Sim环境验证

**任务：** 验证Isaac Sim 4.5.0能正常工作

**验证结果：**
- ✅ `import isaacsim` 成功
- ✅ AppLauncher正常启动
- ✅ GPU检测正常（RTX 4060 Ti, 16GB）
- ✅ Vulkan渲染后端正常
- ⚠️ headless模式初始化时间较长

**关键发现：Isaac Sim脚本必须遵循特定的导入顺序**

```python
# ✅ 正确写法
from isaaclab.app import AppLauncher
app_launcher = AppLauncher(headless=True)
simulation_app = app_launcher.app

# 必须在AppLauncher之后导入omni模块
from pxr import Usd, UsdGeom, Gf
import omni.usd
```

```python
# ❌ 错误写法 - 会导致ModuleNotFoundError
from pxr import Usd  # 在AppLauncher之前导入会失败
from isaaclab.app import AppLauncher
```


---

### 阶段3：Go2-X5 URDF到USD转换

**任务：** 将Go2-X5机器人URDF文件转换为Isaac Sim可用的USD格式

**URDF文件信息：**
- 路径：`Go2-X5-lab/source/robot_lab/data/Robots/go2_x5/go2_x5.urdf`
- 包含：四足底盘（12关节）+ X5机械臂（6关节）+ 头部（2关节）
- 总关节数：49个（含固定关节）
- 机械臂link：arm_base_link, arm_link1~6, arm_eef_link

#### 第一次转换（失败）

**命令：**
```bash
cd /home/tjz/go2_loco_mani/Go2-X5-lab
conda run -n lab python scripts/tools/convert_urdf.py \
  source/robot_lab/data/Robots/go2_x5/go2_x5.urdf \
  /home/tjz/go2_loco_mani/assets/go2_x5.usd \
  --merge-joints \
  --headless
```

**问题现象：**
- 转换成功，但在Isaac Sim中可视化时**机械臂没有显示**
- 只能看到四足底盘，没有arm部分

**根因分析：**
- `--merge-joints`参数会合并所有固定关节（fixed joints）
- Go2-X5的机械臂通过固定关节连接到底盘
- 合并后机械臂的link被合并到了base中，导致视觉上看不到机械臂

**生成的配置：**
```yaml
fix_base: false
merge_fixed_joints: true  # ← 这是问题所在
```

#### 第二次转换（成功）

**改动：** 移除`--merge-joints`参数

**命令：**
```bash
# 先删除旧文件
rm -rf /home/tjz/go2_loco_mani/assets/go2_x5.usd \
       /home/tjz/go2_loco_mani/assets/configuration/ \
       /home/tjz/go2_loco_mani/assets/config.yaml

# 重新转换，不合并固定关节
cd /home/tjz/go2_loco_mani/Go2-X5-lab
conda run -n lab python scripts/tools/convert_urdf.py \
  source/robot_lab/data/Robots/go2_x5/go2_x5.urdf \
  /home/tjz/go2_loco_mani/assets/go2_x5.usd \
  --headless
```

**结果：**
- ✅ 机械臂完整保留，所有arm_link都存在
- ✅ 基座自由（fix_base: false）
- ✅ 18个可动关节正确导入

**生成的配置：**
```yaml
fix_base: false           # ✅ 基座自由
merge_fixed_joints: false  # ✅ 不合并，保留机械臂
drive_type: force
target_type: position
stiffness: 100.0
damping: 1.0
```

**生成的文件：**
```
assets/
├── go2_x5.usd                  # 主USD文件（1.6KB，引用子文件）
├── config.yaml                 # 转换配置记录
└── configuration/
    ├── go2_x5_base.usd        # 基础几何和mesh（37MB）
    ├── go2_x5_physics.usd     # 物理属性（6.6KB）
    └── go2_x5_sensor.usd      # 传感器配置（646B）
```

**教训：**
> 对于带机械臂的复合机器人，**绝对不要使用`--merge-joints`**。该参数会合并固定关节，导致通过固定关节连接的部件（如机械臂底座）被合并消失。


---

### 阶段4：场景与机器人集成（可视化验证）

**任务：** 在Isaac Sim中加载SAGE场景并放置Go2-X5机器人，进行可视化验证

#### 迭代1：基础立方体场景（问题较多）

**实现方式：** 用Cube几何体表示地板、墙体，物体未加载

**问题现象：**
1. **中间出现一条非常长的墙体** - 穿过整个房间
2. **机器人卡在墙里** - spawn位置在墙体内部
3. **场景空荡** - 没有加载任何物体
4. **全部灰色** - 没有颜色和纹理

**截图：** `~/图片/截图/截图 2026-03-17 16-59-02.png`

**根因分析：**

**问题1 - 长墙bug：** 墙体创建逻辑有误。代码先设置scale为`(length, 0.1, height)`（假设墙沿X轴），然后对非X轴方向的墙做旋转。但USD的xform操作顺序是 translate → scale → rotate，scale在rotate之前执行，导致旋转后的墙体尺寸异常。

```python
# ❌ 错误：scale在rotate之前，旋转后尺寸变形
wall_xform.AddTranslateOp().Set(...)
wall_xform.AddScaleOp().Set(Gf.Vec3d(length, 0.1, height))
if abs(dx) > 0.01:
    wall_xform.AddRotateZOp().Set(angle)  # rotate在scale之后
```

**修复：** 改为 translate → rotate → scale 的正确顺序

```python
# ✅ 正确：先旋转再缩放
wall_xform.AddTranslateOp().Set(...)
wall_xform.AddRotateZOp().Set(angle)  # rotate在scale之前
wall_xform.AddScaleOp().Set(Gf.Vec3d(length, thickness, height))
```

**问题2 - 机器人卡墙：** spawn位置硬编码为(3.0, 4.0, 0.5)，恰好在墙体位置。

**修复：** 实现自动寻找空旷位置的算法，遍历候选点并检查与物体的距离。

**问题3 - 没有物体：** 原始脚本只创建了地板和墙体，没有读取objects列表。

**修复：** 从场景JSON读取objects列表，加载对应的PLY mesh文件。

#### 迭代2：加载PLY mesh + 纹理（最终版本）

**改动：**
1. 使用trimesh库加载PLY文件为真实mesh
2. 将mesh转换为USD Mesh（顶点、面、法线、顶点颜色）
3. 加载地板和墙面纹理（PNG材质）
4. 修复墙体旋转顺序
5. 实现自动spawn位置选择

**关键代码 - PLY加载：**
```python
import trimesh

mesh = trimesh.load(ply_path, process=False)
vertices = mesh.vertices
faces = mesh.faces

# 创建USD Mesh
usd_mesh = UsdGeom.Mesh.Define(stage, prim_path)
usd_mesh.GetPointsAttr().Set(Vt.Vec3fArray([
    Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])) for v in vertices
]))

# 顶点颜色
colors = mesh.visual.vertex_colors[:, :3].astype(np.float32) / 255.0
color_primvar = UsdGeom.PrimvarsAPI(usd_mesh).CreatePrimvar(
    "displayColor", Sdf.ValueTypeNames.Color3fArray, UsdGeom.Tokens.vertex
)
color_primvar.Set(Vt.Vec3fArray([
    Gf.Vec3f(float(c[0]), float(c[1]), float(c[2])) for c in colors
]))
```

**遇到的类型错误：**
```
Boost.Python.ArgumentError: Python argument types in
    Vec3f.__init__(Vec3f, numpy.float32, numpy.float32, numpy.float32)
did not match C++ signature:
    __init__(_object*, float, float, float)
```

**原因：** `Gf.Vec3f`不接受numpy.float32类型，必须转换为Python原生float

**修复：** 将`Gf.Vec3f(*v)`改为`Gf.Vec3f(float(v[0]), float(v[1]), float(v[2]))`

**最终结果：**
- ✅ 场景物体以真实PLY mesh形状显示
- ✅ 物体带有顶点颜色
- ✅ 地板和墙面有纹理
- ✅ 墙体位置和方向正确
- ✅ Go2-X5机器人完整显示（含机械臂）
- ✅ 机器人在空旷位置，不与物体碰撞

**运行命令：**
```bash
cd /home/tjz/go2_loco_mani
conda run -n lab python scripts/visualize_scene_robot.py
```


---

### 阶段5：批量场景处理

**任务：** 批量分析SAGE场景，为每个场景生成机器人spawn位置配置

**实现：** `scripts/batch_process_scenes.py`
- 直接读取ZIP文件中的JSON（不需要解压）
- 提取房间类型、尺寸、物体数量等元数据
- 为每个房间生成4个候选spawn位置（center, near_entrance, corner_1, corner_2）

**运行命令：**
```bash
python scripts/batch_process_scenes.py \
  --scenes_dir datasets/sage-10k/scenes \
  --output configs/batch_scene_configs.yaml \
  --max_scenes 50
```

**结果：**
- ✅ 50个场景全部处理成功（0失败）
- ✅ 生成配置文件 `configs/batch_scene_configs.yaml`
- 总房间数：50
- 房间类型：26种

---

### 阶段7：替换X5A机械臂 + 添加平行夹爪

**任务：** 将Go2-X5的旧X5机械臂替换为X5A机械臂（含平行夹爪），使机器人具备抓取能力

**新臂来源：** `/home/tjz/go2_loco_mani/X5/X5A/urdf/X5A.urdf`

**新旧对比：**

| 项目 | 旧臂(X5) | 新臂(X5A) |
|------|----------|-----------|
| 旋转关节 | 6个 (arm_joint1~6) | 6个 (arm_joint1~6) |
| 夹爪关节 | 无 | 2个棱柱关节 (arm_joint7, arm_joint8) |
| 总DOF | 6 | 8 |
| 末端 | 虚拟arm_eef_link | 平行夹爪(arm_link7, arm_link8) |
| mesh文件 | base_link~link6 (13MB) | base_link~link8 (8.5MB) |

**操作步骤：**

1. **备份旧mesh + 复制新mesh：**
```bash
cp -r Go2-X5-lab/source/robot_lab/data/Robots/go2_x5/meshes/X5/ \
      Go2-X5-lab/source/robot_lab/data/Robots/go2_x5/meshes/X5_backup/
cp /home/tjz/go2_loco_mani/X5/X5A/meshes/*.STL \
   Go2-X5-lab/source/robot_lab/data/Robots/go2_x5/meshes/X5/
```

2. **修改URDF（go2_x5.urdf line 771~1018）：**
   - 更新arm_base_link~arm_link6的inertial数据（mass, inertia, CoM）为X5A值
   - 更新joint origin偏移为X5A值（反映新硬件尺寸）
   - 更新joint3 rpy从`-3.1416`改为`3.1416`（X5A的旋转方向）
   - 保留旧的关节限位（已调优，X5A的±10rad是SolidWorks默认值）
   - 保留旧的dynamics（damping 0.3~0.5, friction 0.1）
   - collision改为使用实际STL mesh（旧版部分link用简化cylinder）
   - 新增arm_link7/arm_link8（夹爪手指）+ arm_joint7/arm_joint8（prismatic）
   - arm_eef_link重定位到夹爪中心（xyz="0.08657 0 0"）

3. **夹爪关节参数：**
   - 类型：prismatic（棱柱/平移关节）
   - arm_joint7：axis Y，range 0~0.044m（手指1向+Y打开）
   - arm_joint8：axis -Y，range 0~0.044m（手指2向-Y打开）
   - dynamics：damping="0.1" friction="0.05"
   - effort="20" velocity="1"

4. **重新转换USD：**
```bash
cd /home/tjz/go2_loco_mani/Go2-X5-lab
conda run -n lab python scripts/tools/convert_urdf.py \
  source/robot_lab/data/Robots/go2_x5/go2_x5.urdf \
  /home/tjz/go2_loco_mani/assets/go2_x5.usd \
  --headless
```

**验证结果：**
- ✅ USD转换成功，51个joint prims（含fixed joints）
- ✅ 6个PhysicsRevoluteJoint（arm_joint1~6）
- ✅ 2个PhysicsPrismaticJoint（arm_joint7, arm_joint8）
- ✅ 总可动关节：20个（12腿 + 6臂 + 2夹爪）
- ✅ go2_x5_base.usd 31MB（含新mesh）
- ✅ arm_joint8添加mimic标签跟随arm_joint7对称运动

---

## 踩坑记录

### 坑1：Isaac Sim模块导入顺序

**现象：**
```
ModuleNotFoundError: No module named 'omni.isaac.core'
```

**定位方式：** 对比Go2-X5-lab中的工作脚本（如list_envs.py），发现它们都在AppLauncher之后才导入omni模块。

**根因：** Isaac Sim的omni模块是通过Kit框架动态加载的，必须在AppLauncher启动后才可用。

**解决方案：**
```python
# 1. 先启动AppLauncher
from isaaclab.app import AppLauncher
app_launcher = AppLauncher(headless=True)
simulation_app = app_launcher.app

# 2. 然后才能导入omni模块
from pxr import Usd, UsdGeom
import omni.usd
```

---

### 坑2：--merge-joints导致机械臂消失

**现象：** URDF转USD后，Isaac Sim中只能看到四足底盘，机械臂不见了。

**定位方式：** 
1. 检查URDF文件确认机械臂link存在（arm_base_link ~ arm_link6）
2. 检查转换配置文件config.yaml发现`merge_fixed_joints: true`
3. 分析URDF发现机械臂通过固定关节连接到底盘

**根因：** `--merge-joints`合并了所有固定关节，机械臂的固定连接被合并，导致arm link被合并到base中。

**解决方案：** 重新转换，不使用`--merge-joints`参数。

---

### 坑3：USD墙体旋转变形

**现象：** 场景中出现一条穿过整个房间的超长墙体。

**定位方式：** 检查墙体的start_point和end_point，发现是Y轴方向的墙（east/west wall），但scale是按X轴方向设置的。

**根因：** USD xform操作按添加顺序执行。代码先scale再rotate，导致scale在世界坐标系下执行后，rotate改变了方向但尺寸已经固定。

**解决方案：** 改为 translate → rotate → scale 顺序，确保scale在局部坐标系下执行。

---

### 坑4：Gf.Vec3f不接受numpy.float32

**现象：**
```
Boost.Python.ArgumentError: Python argument types in
    Vec3f.__init__(Vec3f, numpy.float32, numpy.float32, numpy.float32)
did not match C++ signature
```

**定位方式：** 错误信息明确指出类型不匹配。

**根因：** trimesh加载PLY后，顶点坐标是numpy.float32类型，而pxr的Gf.Vec3f只接受Python原生float。

**解决方案：** 显式转换：`Gf.Vec3f(float(v[0]), float(v[1]), float(v[2]))`

---

### 坑5：URDF中文材质名称警告

**现象：**
```
[Warning] The path 深色橡胶_001-effect is not a valid usd path, modifying to a______________001_effect
```

**根因：** USD路径不支持中文字符，URDF中的中文材质名称需要转换。

**解决方案：** Isaac Sim自动将中文转换为下划线替代，不影响功能，可以忽略。

---

### 坑6：Isaac Sim GUI模式启动慢/黑屏

**现象：** 运行可视化脚本后，Isaac Sim窗口长时间黑屏（5-10分钟）。

**定位方式：** 通过`ps aux`查看进程状态，CPU占用188%说明在加载中。

**根因：** 
- 首次启动需要编译着色器缓存
- 加载大量扩展（约150个）
- GPU初始化和IOMMU警告

**解决方案：** 耐心等待5-10分钟，后续启动会更快（着色器已缓存）。

---

### 坑7：robot_lab模块未安装

**现象：**
```
ModuleNotFoundError: No module named 'robot_lab'
```

**根因：** Go2-X5-lab的robot_lab扩展未安装到conda环境中。

**解决方案：**
```bash
cd /home/tjz/go2_loco_mani/Go2-X5-lab
conda run -n lab python -m pip install -e source/robot_lab
```


---

## 素材积累

### 关键截图

| 截图 | 说明 | 路径 |
|------|------|------|
| 场景可视化（问题版） | 墙体bug + 机器人卡墙 | `~/图片/截图/截图 2026-03-17 16-59-02.png` |
| 场景可视化（修复版） | PLY mesh + 纹理 + 机械臂 | 待截图 |

### 数据集统计

**SAGE-10k场景分布（前50个场景）：**

| 房间类型 | 数量 |
|----------|------|
| master bedroom | 7 |
| living room | 5 |
| kitchen | 4 |
| warehouse | 4 |
| bathroom | 3 |
| 其他（21种） | 27 |

### Go2-X5机器人规格

| 参数 | 值 |
|------|-----|
| 总关节数 | 20个可动关节 |
| 腿部关节 | 12个（4腿 × 3关节：hip, thigh, calf） |
| 机械臂关节 | 6个（arm_joint1~6，revolute） |
| 夹爪关节 | 2个（arm_joint7~8，prismatic，开合范围0~0.044m） |
| 基座高度 | ~0.4m |
| 机械臂型号 | X5A（含平行夹爪） |
| USD主文件 | 1.6KB（引用子文件） |
| USD几何文件 | 31MB（go2_x5_base.usd） |

### Git提交记录

| 时间 | Commit | 说明 |
|------|--------|------|
| 2026-03-17 | Initial commit | 项目初始化，阶段1-3和阶段5 |
| 2026-03-17 | docs: Add experiment logs | 添加实验记录和踩坑记录 |
| 2026-03-17 | feat: Add GUI visualization | 可视化验证脚本 |
| 2026-03-17 | fix: Improve visualization | 添加物体加载，修复spawn位置 |
| 2026-03-17 | fix: Reconvert robot USD | 移除merge-joints保留机械臂 |
| 2026-03-17 | fix: Rewrite visualization | 修复墙体旋转，加载PLY mesh |
| 2026-03-17 | fix: Vec3f type conversion | 修复numpy.float32类型兼容 |

---

## 关键文件路径速查

### 数据集
```bash
SAGE-10k数据集: /home/tjz/go2_loco_mani/datasets/sage-10k/
示例场景（已解压）: /home/tjz/go2_loco_mani/datasets/sage-10k/scenes/test_scene/
```

### 机器人模型
```bash
Go2-X5 URDF: /home/tjz/go2_loco_mani/Go2-X5-lab/source/robot_lab/data/Robots/go2_x5/go2_x5.urdf
Go2-X5 USD: /home/tjz/go2_loco_mani/assets/go2_x5.usd
Go2-X5 Mesh: /home/tjz/go2_loco_mani/Go2-X5-lab/source/robot_lab/data/Robots/go2_x5/meshes/
X5A原始URDF: /home/tjz/go2_loco_mani/X5/X5A/urdf/X5A.urdf
旧X5 Mesh备份: /home/tjz/go2_loco_mani/Go2-X5-lab/source/robot_lab/data/Robots/go2_x5/meshes/X5_backup/
```

### 脚本
```bash
URDF转换: /home/tjz/go2_loco_mani/Go2-X5-lab/scripts/tools/convert_urdf.py
可视化验证: /home/tjz/go2_loco_mani/scripts/visualize_scene_robot.py
批量场景处理: /home/tjz/go2_loco_mani/scripts/batch_process_scenes.py
场景机器人集成: /home/tjz/go2_loco_mani/scripts/integrate_robot_scene.py
```

### 配置文件
```bash
场景-机器人配置: /home/tjz/go2_loco_mani/configs/scene_robot_configs.yaml
批量场景配置: /home/tjz/go2_loco_mani/configs/batch_scene_configs.yaml
URDF转换配置: /home/tjz/go2_loco_mani/assets/config.yaml
```

### SAGE源码参考
```bash
MCP Extension: /home/tjz/go2_loco_mani/sage/server/isaacsim/isaac.sim.mcp_extension/
场景工具: /home/tjz/go2_loco_mani/sage/server/isaacsim/isaac.sim.mcp_extension/isaac_sim_mcp_extension/scene/utils.py
场景模型: /home/tjz/go2_loco_mani/sage/server/isaacsim/isaac.sim.mcp_extension/isaac_sim_mcp_extension/scene/models.py
```

---

## 使用指南

### 1. 可视化验证场景和机器人

```bash
cd /home/tjz/go2_loco_mani

# GUI模式（默认）
conda run -n lab python scripts/visualize_scene_robot.py

# 指定不同场景
conda run -n lab python scripts/visualize_scene_robot.py \
  --scene_path datasets/sage-10k/scenes/test_scene

# headless模式
conda run -n lab python scripts/visualize_scene_robot.py --headless
```

**GUI操作：**
- 鼠标拖拽旋转视角
- 滚轮缩放
- 点击Play按钮启动物理仿真
- Ctrl+C退出

### 2. 转换URDF到USD

```bash
cd /home/tjz/go2_loco_mani/Go2-X5-lab
conda run -n lab python scripts/tools/convert_urdf.py \
  source/robot_lab/data/Robots/go2_x5/go2_x5.urdf \
  /home/tjz/go2_loco_mani/assets/go2_x5.usd \
  --headless
# 注意：不要加 --merge-joints！
```

### 3. 批量处理场景

```bash
cd /home/tjz/go2_loco_mani
conda run -n lab python scripts/batch_process_scenes.py --max_scenes 50
```

### 4. 下载SAGE数据集

```bash
cd /home/tjz/go2_loco_mani/datasets/sage-10k
conda run -n lab huggingface-cli download nvidia/SAGE-10k \
  --repo-type dataset --local-dir ./ --max-workers 4
```

---

## 后续计划

### 短期
1. **任务设计** - 定义loco-manipulation任务（导航+抓取），设计奖励函数
2. **数据采集准备** - 设计观测空间（相机、本体感知）和动作空间（关节命令）

### 中期
1. **批量数据采集** - 多场景并行仿真，自动化数据收集
2. **通信接口** - 实现外部策略模型调用接口

### 长期
1. **VLA模型训练** - 选择合适的VLA架构（考虑16GB显存限制），使用微调方案
2. **模型部署与评估** - 多场景泛化测试

---

## 更新日志

### 2026-03-17

**完成的工作：**
- ✅ 创建项目目录结构和Git仓库
- ✅ 安装robot_lab扩展
- ✅ 完成SAGE-10k数据集下载（526个场景）
- ✅ 解压并分析示例场景结构（JSON + PLY + 纹理）
- ✅ 完成Go2-X5 URDF到USD转换（两次迭代，修复机械臂问题）
- ✅ 创建可视化验证脚本（三次迭代，修复墙体/物体/类型问题）
- ✅ 批量处理50个场景并生成spawn配置
- ✅ 完成详细开发文档

**解决的问题：**
1. Isaac Sim模块导入顺序问题
2. --merge-joints导致机械臂消失
3. 墙体旋转变形（xform操作顺序）
4. 机器人卡在墙里（spawn位置）
5. 场景物体未加载（PLY mesh导入）
6. numpy.float32与Gf.Vec3f类型不兼容
7. robot_lab模块未安装

**Git提交：** 7次commit，全部推送到GitHub

### 2026-03-17（晚）

**完成的工作：**
- ✅ 替换X5机械臂为X5A（含平行夹爪）
- ✅ 更新URDF：X5A inertial数据、joint origin、新增arm_joint7/8棱柱关节
- ✅ 备份旧mesh，复制X5A mesh（含link7.STL、link8.STL夹爪手指）
- ✅ 重新转换USD，验证20个可动关节（12腿+6臂+2夹爪）

---

*最后更新：2026-03-17 22:00*
