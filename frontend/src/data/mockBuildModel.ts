/** Mock 拼装数据 - 简易小车 */

import type { BuildModel } from "@/types/builder3d"

export const mockBuildModel: BuildModel = {
  setId: "3001-mock",
  setName: "简易小车",
  totalSteps: 6,
  totalBricks: 9,
  basePlate: { width: 4, length: 8 },
  steps: [
    {
      stepNumber: 1,
      description: "放置绿色底板作为基础",
      bricksToAdd: [
        {
          id: "base-1",
          partId: "3001",
          name: "Plate 4x8",
          color: "#00852B",
          colorName: "Green",
          size: { x: 4, y: 1, z: 8 },
          position: { x: 0, y: 0, z: 0 },
        },
      ],
    },
    {
      stepNumber: 2,
      description: "在底板左侧放置两个红色 2x2 砖",
      bricksToAdd: [
        {
          id: "brick-1",
          partId: "3001",
          name: "Brick 2x2",
          color: "#E3000B",
          colorName: "Red",
          size: { x: 2, y: 1, z: 2 },
          position: { x: 0, y: 1, z: 0 },
        },
        {
          id: "brick-2",
          partId: "3001",
          name: "Brick 2x2",
          color: "#E3000B",
          colorName: "Red",
          size: { x: 2, y: 1, z: 2 },
          position: { x: 2, y: 1, z: 0 },
        },
      ],
    },
    {
      stepNumber: 3,
      description: "在红色砖上方放置白色 2x4 砖作为车身",
      bricksToAdd: [
        {
          id: "brick-3",
          partId: "3001",
          name: "Brick 2x4",
          color: "#F4F4F4",
          colorName: "White",
          size: { x: 2, y: 1, z: 4 },
          position: { x: 0, y: 2, z: 1 },
        },
      ],
    },
    {
      stepNumber: 4,
      description: "在车身前部添加黄色 1x2 砖作为车顶",
      bricksToAdd: [
        {
          id: "brick-4",
          partId: "3001",
          name: "Brick 1x2",
          color: "#F5CD2F",
          colorName: "Yellow",
          size: { x: 1, y: 1, z: 2 },
          position: { x: 0, y: 3, z: 2 },
        },
      ],
    },
    {
      stepNumber: 5,
      description: "在底板下方安装黑色轮子",
      bricksToAdd: [
        {
          id: "wheel-1",
          partId: "3001",
          name: "Wheel",
          color: "#1B2A34",
          colorName: "Black",
          size: { x: 1, y: 1, z: 1 },
          position: { x: 0, y: 0, z: -1 },
        },
        {
          id: "wheel-2",
          partId: "3001",
          name: "Wheel",
          color: "#1B2A34",
          colorName: "Black",
          size: { x: 1, y: 1, z: 1 },
          position: { x: 3, y: 0, z: -1 },
        },
        {
          id: "wheel-3",
          partId: "3001",
          name: "Wheel",
          color: "#1B2A34",
          colorName: "Black",
          size: { x: 1, y: 1, z: 1 },
          position: { x: 0, y: 0, z: 8 },
        },
        {
          id: "wheel-4",
          partId: "3001",
          name: "Wheel",
          color: "#1B2A34",
          colorName: "Black",
          size: { x: 1, y: 1, z: 1 },
          position: { x: 3, y: 0, z: 8 },
        },
      ],
    },
    {
      stepNumber: 6,
      description: "在车顶添加蓝色透明 1x1 砖作为车灯",
      bricksToAdd: [
        {
          id: "light-1",
          partId: "3001",
          name: "Brick 1x1",
          color: "#00BCD4",
          colorName: "Cyan",
          size: { x: 1, y: 1, z: 1 },
          position: { x: 0, y: 4, z: 2 },
        },
      ],
    },
  ],
}
