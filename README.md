# nav2_robocon — ROBOCON 2026 全向导航

基于 ROS 2 Nav2 (MPPI) 的全向移动机器人自主导航包。

## 构建

```bash
cd ~/nav2_ws_new
colcon build --packages-select nav2_robocon_msgs nav2_robocon
source install/setup.bash
```

## 启动

```bash
ros2 launch nav2_robocon third_area_single.launch.py team:=red   # 红队
ros2 launch nav2_robocon third_area_single.launch.py team:=blue  # 蓝队
```

## 发送导航目标

### 方式一：`/navigate_to_xyaw` action（推荐，直接输入角度）

类型 `nav2_robocon_msgs/action/NavigateToXYaw`，goal 字段为 `x`, `y`, `yaw`，yaw 单位**弧度**。

```bash
# 导航到 (7.7, 1.6)，朝向 90°
ros2 action send_goal /navigate_to_xyaw nav2_robocon_msgs/action/NavigateToXYaw \
  "{x: 7.7, y: 1.6, yaw: 1.57}" --feedback

# 导航到 (6.0, 2.5)，朝向 -90°（-π/2）
ros2 action send_goal /navigate_to_xyaw nav2_robocon_msgs/action/NavigateToXYaw \
  "{x: 6.0, y: 2.5, yaw: -1.57}" --feedback
```

**常用角度速查：**

| 角度 | 弧度 | 朝向 |
|------|------|------|
| 0° | 0.0 | → +x |
| 90° | 1.57 | → +y |
| 180° | 3.14 | → -x |
| -90° | -1.57 | → -y |

### 方式二：`/move_base_simple/goal`（PoseStamped，兼容 RViz）

```bash
ros2 topic pub /move_base_simple/goal geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: 'map'}, \
    pose: {position: {x: 7.7, y: 1.6}, \
           orientation: {z: 0.707, w: 0.707}}}" -1
```

## 行为说明

1. 收到 `/navigate_to_xyaw` action goal 后**立即锁定 yaw**（通过 `/desired_yaw` 控制机器人保持目标朝向）
2. 转发到 Nav2 `NavigateToPose` 导航到目标点
3. **ramp 区域自动处理**（由 `ramp_zone_manager` 负责，无需手动干预）：
   - 进入斜坡 → 悬挂升高 + 最低限速
   - 离开斜坡 → 悬挂降低
   - yaw 在斜坡上保持锁定
4. 到达目标后解除 yaw 锁定，等待下一个目标
5. 导航中收到新 action goal 会抢占当前目标

## 节点架构

```
/navigate_to_xyaw action [x,y,yaw]
        │
        ▼
 navigate_to_xyaw_server  ──► /desired_yaw (Float32)
        │
        ▼
 NavigateToPose action ──► Nav2 (MPPI controller)
        │
        ▼
    /cmd_vel ──► ramp_zone_manager ──► /cmd_vel_adjusted ──► cmd_vel_bridge ──► 底盘
                     │
        /odin1/relocation (位姿)
```

## Ramp 斜坡参数

`ramp_zone_manager` 的可配置参数，通过 launch 或 yaml 传入：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `team` | red | 队伍，影响 ramp Y 默认值 |
| `ramp_x_min` | 8.9 | 斜坡 X 起点 (m) |
| `ramp_x_max` | 10.4 | 斜坡 X 终点 (m) |
| `ramp_y_min` | 蓝 3.1 / 红 -4.6 | 斜坡 Y 下界 (m) |
| `ramp_y_max` | 蓝 4.6 / 红 -3.1 | 斜坡 Y 上界 (m) |
| `min_ramp_speed` | 0.25 | 斜坡区最低速 (m/s) |
| `suspension_ramp` | 75.0 | 斜坡悬挂高度 (mm) |
| `suspension_flat` | 30.0 | 平地悬挂高度 (mm) |
| `yaw_kp` | 2.0 | yaw 保持 P 增益 |
| `yaw_max_vel` | 2.0 | yaw 最大角速度 (rad/s) |

**覆盖参数示例：**

```bash
ros2 run nav2_robocon ramp_zone_manager --ros-args \
  -p team:=blue \
  -p ramp_x_min:=9.0 \
  -p ramp_y_min:=3.0 \
  -p ramp_y_max:=4.5
```

或在 launch 文件中：

```python
Node(
    package="nav2_robocon",
    executable="ramp_zone_manager",
    parameters=[{
        "team": "blue",
        "ramp_y_min": 3.1,
        "ramp_y_max": 4.6,
    }],
)
```

## 改地图时需同步修改

| 文件 | 改什么 |
|------|--------|
| `maps/field_red.pgm` | 新地图图片（红队） |
| `maps/field_blue.pgm` | 新地图图片（蓝队） |
| `maps/field_red.yaml` | `resolution`, `origin` |
| `maps/field_blue.yaml` | `resolution`, `origin` |
| `scripts/generate_map.py` | 场地尺寸常量（如用脚本生成） |
| ramp 参数 | `ramp_x_min/max`, `ramp_y_min/max`（见上表） |

`nav2_params.yaml`、悬挂高度、限速、到位精度等**不需要随着地图改动**。
