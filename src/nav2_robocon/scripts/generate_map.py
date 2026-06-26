#!/usr/bin/env python3
"""生成 ROBOCON 场地静态地图 (PGM + YAML)
红蓝是完全不同的 relocalization 坐标系，各自只画自己的障碍物。

蓝队坐标系下：
  - 地图左下角 origin: (-0.4, -1.4) 单位 m
  - 地图边界: x(-0.4, 11.6), y(-1.4, 4.6)
  - 梅林区: x(2.8, 7.6), y(-0.2, 3.4)
  - 高台: x=9.05, y(-1.4, 3.1)
  - 斜边边界墙: y=3.1, x(8.9, 10.4)
  - 斜坡: x(8.9, 10.4), y(3.1, 4.6)

红队坐标系下：
  - 地图左下角 origin: (-0.4, -4.6) 单位 m
  - 地图边界: x(-0.4, 11.6), y(-4.6, 1.4)
  - 梅林区: x(2.8, 7.6), y(-3.4, 0.2)
  - 高台: x=9.05, y(-3.1, 1.4)
  - 斜边边界墙: y=-3.1, x(8.9, 10.4)
  - 斜坡: x(8.9, 10.4), y(-4.6, -3.1)
"""

import numpy as np
import os

# ============================================================
# 场地尺寸（单位：米）—— 改地图时只改这里即可
# ============================================================
BLUE_ORIGIN_X, BLUE_ORIGIN_Y = -0.4, -1.4
RED_ORIGIN_X,  RED_ORIGIN_Y  = -0.4, -4.6

FIELD_X_MIN, FIELD_X_MAX = -0.4, 11.6
BLUE_Y_MIN,  BLUE_Y_MAX  = -1.4, 4.6
RED_Y_MIN,   RED_Y_MAX   = -4.6, 1.4

# 高台 (obstacle)
PLATFORM_X       = 9.05      # m
BLUE_PLATFORM_Y  = (-1.4, 3.1)
RED_PLATFORM_Y   = (-3.1, 1.4)

# 斜边边界墙
SLANT_WALL_X     = (8.9, 10.4)
BLUE_SLANT_Y     = 3.1
RED_SLANT_Y      = -3.1

# 斜坡区域 (free space, 不画墙)
RAMP_X           = (8.9, 10.4)
BLUE_RAMP_Y      = (3.1, 4.6)
RED_RAMP_Y       = (-4.6, -3.1)

RESOLUTION = 0.05  # m/pixel

# ============================================================
# 以下为绘图逻辑，一般不需要改动
# ============================================================


def make_grid(origin_x, origin_y, y_min, y_max):
    """创建空白地图网格 (254 = 自由空间)"""
    width  = int((FIELD_X_MAX - FIELD_X_MIN) / RESOLUTION)
    height = int((y_max - y_min) / RESOLUTION)
    return np.full((height, width), 254, dtype=np.uint8), width, height, origin_x, origin_y, y_min


def world_to_pixel(x, y, origin_x, width, origin_y, height, y_min):
    """世界坐标 → 像素坐标"""
    px = int((x - origin_x) / RESOLUTION)
    py = int((y - y_min) / RESOLUTION)
    return max(0, min(width - 1, px)), max(0, min(height - 1, py))


def draw_wall(grid, x_min, x_max, y_min, y_max,
              origin_x, width, origin_y, height, y_min_field):
    """在网格上画墙 (0 = 占用)"""
    px_min, py_min = world_to_pixel(x_min, y_min, origin_x, width, origin_y, height, y_min_field)
    px_max, py_max = world_to_pixel(x_max, y_max, origin_x, width, origin_y, height, y_min_field)
    if px_max - px_min < 2:
        px_max = min(width - 1, px_min + 2)
    if py_max - py_min < 2:
        py_max = min(height - 1, py_min + 2)
    grid[py_min:py_max + 1, px_min:px_max + 1] = 0


def generate_map(team: str, output_dir: str):
    """生成单队地图"""
    if team == "blue":
        origin_x, origin_y = BLUE_ORIGIN_X, BLUE_ORIGIN_Y
        y_min, y_max = BLUE_Y_MIN, BLUE_Y_MAX
        platform_y = BLUE_PLATFORM_Y
        slant_y   = BLUE_SLANT_Y
    else:
        origin_x, origin_y = RED_ORIGIN_X, RED_ORIGIN_Y
        y_min, y_max = RED_Y_MIN, RED_Y_MAX
        platform_y = RED_PLATFORM_Y
        slant_y   = RED_SLANT_Y

    grid, width, height, _, _, _ = make_grid(origin_x, origin_y, y_min, y_max)

    # 1. 场地四周边界
    draw_wall(grid, FIELD_X_MIN, FIELD_X_MAX, y_min, y_min + 0.1,
              origin_x, width, origin_y, height, y_min)
    draw_wall(grid, FIELD_X_MIN, FIELD_X_MAX, y_max - 0.1, y_max,
              origin_x, width, origin_y, height, y_min)
    draw_wall(grid, FIELD_X_MIN, FIELD_X_MIN + 0.1, y_min, y_max,
              origin_x, width, origin_y, height, y_min)
    draw_wall(grid, FIELD_X_MAX - 0.1, FIELD_X_MAX, y_min, y_max,
              origin_x, width, origin_y, height, y_min)

    # 2. 高台 (垂直墙)
    draw_wall(grid, PLATFORM_X, PLATFORM_X + 0.1, platform_y[0], platform_y[1],
              origin_x, width, origin_y, height, y_min)

    # 3. 斜边边界墙
    draw_wall(grid, SLANT_WALL_X[0], SLANT_WALL_X[1], slant_y, slant_y + 0.1,
              origin_x, width, origin_y, height, y_min)

    # PGM 输出（翻 Y 轴）
    grid_flipped = np.flipud(grid)
    pgm_path = os.path.join(output_dir, f"field_{team}.pgm")
    with open(pgm_path, "wb") as f:
        f.write(f"P5\n{width} {height}\n255\n".encode())
        f.write(grid_flipped.tobytes())

    yaml_path = os.path.join(output_dir, f"field_{team}.yaml")
    with open(yaml_path, "w") as f:
        f.write(f"image: field_{team}.pgm\n")
        f.write(f"resolution: {RESOLUTION}\n")
        f.write(f"origin: [{origin_x}, {origin_y}, 0.0]\n")
        f.write("negate: 0\n")
        f.write("occupied_thresh: 0.65\n")
        f.write("free_thresh: 0.196\n")

    print(f"[{team}] Generated {pgm_path} ({width}x{height})")


if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maps")
    os.makedirs(output_dir, exist_ok=True)
    generate_map("red", output_dir)
    generate_map("blue", output_dir)
    print("Done!")
