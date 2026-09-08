// 物体检测 Provider 链（PRD §7）：
//   1) yolo      YOLOv8n ONNX Runtime Web（需 web/models/yolov8n.onnx + CDN ort）
//   2) saliency  演示检测器：颜色饱和度连通域 → "红色的东西"等伪框（无模型依赖）
//   3) static    静态演示场景：直接返回场景内已知物件框
//
// 关键修复：
// - 真实摄像头 auto/yolo 模式下，YOLO 加载失败不再降级成“橙色的东西”
// - 检查 HTML / Git LFS pointer / JSON / 异常小模型
// - 修复 YOLOv8 [1,84,8400] 与 [1,8400,84] 输出解析
// - 不再依赖 HEAD 请求判断模型存在

import { CONFIG } from './config.js';

export const COCO_ZH = {
  person: '人',
  bicycle: '自行车',
  car: '小汽车',
  motorcycle: '摩托车',
  airplane: '飞机',
  bus: '公交车',
  train: '火车',
  truck: '卡车',
  boat: '船',
  'traffic light': '红绿灯',
  'fire hydrant': '消防栓',
  'stop sign': '停车牌',
  'parking meter': '停车计费表',
  bench: '长椅',
  bird: '小鸟',
  cat: '猫',
  dog: '狗',
  horse: '马',
  sheep: '绵羊',
  cow: '牛',
  elephant: '大象',
  bear: '熊',
  zebra: '斑马',
  giraffe: '长颈鹿',
  backpack: '书包',
  umbrella: '雨伞',
  handbag: '手提包',
  tie: '领带',
  suitcase: '行李箱',
  frisbee: '飞盘',
  skis: '滑雪板',
  snowboard: '滑雪板',
  'sports ball': '球',
  kite: '风筝',
  'baseball bat': '棒球棒',
  'baseball glove': '棒球手套',
  skateboard: '滑板',
  surfboard: '冲浪板',
  'tennis racket': '网球拍',
  bottle: '瓶子',
  'wine glass': '酒杯',
  cup: '杯子',
  fork: '叉子',
  knife: '刀',
  spoon: '勺子',
  bowl: '碗',
  banana: '香蕉',
  apple: '苹果',
  sandwich: '三明治',
  orange: '橙子',
  broccoli: '西兰花',
  carrot: '胡萝卜',
  'hot dog': '热狗',
  pizza: '披萨',
  donut: '甜甜圈',
  cake: '蛋糕',
  chair: '椅子',
  couch: '沙发',
  'potted plant': '盆栽',
  bed: '床',
  'dining table': '桌子',
  toilet: '马桶',
  tv: '电视机',
  laptop: '笔记本电脑',
  mouse: '鼠标',
  remote: '遥控器',
  keyboard: '键盘',
  'cell phone': '手机',
  microwave: '微波炉',
  oven: '烤箱',
  toaster: '烤面包机',
  sink: '水槽',
  refrigerator: '冰箱',
  book: '书',
  clock: '时钟',
  vase: '花瓶',
  scissors: '剪刀',
  'teddy bear': '泰迪熊',
  'hair drier': '吹风机',
  toothbrush: '牙刷',
};

const COCO_CLASSES = Object.keys(COCO_ZH);

const HUE_NAMES = [
  [15, '红色的'],
  [45, '橙色的'],
  [75, '黄色的'],
  [165, '绿色的'],
  [260, '蓝色的'],
  [300, '紫色的'],
  [345, '粉色的'],
  [361, '红色的'],
];

function hueName(h) {
  for (const [max, name] of HUE_NAMES) {
    if (h < max) return name;
  }
  return '彩色的';
}

function clampBox(b, w, h) {
  const x = Math.max(0, Math.min(b[0], w - 1));
  const y = Math.max(0, Math.min(b[1], h - 1));
  const bw = Math.max(1, Math.min(b[2], w - x));
  const bh = Math.max(1, Math.min(b[3], h - y));
  return [x, y, bw, bh];
}

// ============================================================
// 1. YOLOv8n ONNX
// ============================================================

export class YoloDetector {
  constructor({
    modelUrl = '/models/yolov8n.onnx',
  } = {}) {
    this.name = 'yolo';
    this.modelUrl = modelUrl;
    this.session = null;
  }

  static async available(
    modelUrl = '/models/yolov8n.onnx'
  ) {
    try {
      const res = await fetch(modelUrl, {
        method: 'GET',
        headers: {
          Range: 'bytes=0-255',
        },
        cache: 'no-store',
      });

      return res.ok;
    } catch {
      return false;
    }
  }

  async init() {
    // ------------------------------
    // 加载 ONNX Runtime Web
    // ------------------------------

    if (!window.ort) {
      await new Promise((resolve, reject) => {
        const s = document.createElement('script');

        s.src =
          'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.18.0/dist/ort.min.js';

        s.onload = resolve;

        s.onerror = () =>
          reject(
            new Error(
              'ONNX Runtime Web 加载失败'
            )
          );

        document.head.appendChild(s);
      });
    }

    window.ort.env.wasm.wasmPaths =
      'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.18.0/dist/';

    // ------------------------------
    // 下载 ONNX
    // ------------------------------

    const res = await fetch(
      this.modelUrl,
      {
        cache: 'no-store',
      }
    );

    if (!res.ok) {
      throw new Error(
        `模型请求失败：HTTP ${res.status} ${this.modelUrl}`
      );
    }

    const contentType =
      (
        res.headers.get('content-type') ||
        ''
      ).toLowerCase();

    const buf =
      await res.arrayBuffer();

    // ------------------------------
    // 检查模型是否是假文件
    // ------------------------------

    const firstBytes =
      new Uint8Array(
        buf.slice(
          0,
          Math.min(
            buf.byteLength,
            256
          )
        )
      );

    const head =
      new TextDecoder(
        'utf-8',
        {
          fatal: false,
        }
      )
        .decode(firstBytes)
        .trim();

    console.info(
      '[detector] 模型请求结果',
      {
        url: this.modelUrl,
        status: res.status,
        contentType,
        bytes: buf.byteLength,
        sizeMB:
          (
            buf.byteLength /
            1024 /
            1024
          ).toFixed(2),
      }
    );

    // HTML fallback
    if (
      contentType.includes(
        'text/html'
      ) ||
      /^<!doctype html/i.test(
        head
      ) ||
      /^<html/i.test(
        head
      )
    ) {
      throw new Error(
        `加载到的是 HTML，不是 ONNX。请检查 ${this.modelUrl} 路径`
      );
    }

    // Git LFS pointer
    if (
      head.includes(
        'git-lfs.github.com/spec/v1'
      )
    ) {
      throw new Error(
        '加载到的是 Git LFS pointer，不是真实 ONNX 文件。请执行 git lfs pull 或重新下载真实模型'
      );
    }

    // JSON 错误返回
    if (
      contentType.includes(
        'application/json'
      ) ||
      head.startsWith('{') ||
      head.startsWith('[')
    ) {
      throw new Error(
        `加载到的是 JSON/错误响应，不是 ONNX。请检查 ${this.modelUrl}`
      );
    }

    // 文件明显太小
    if (
      buf.byteLength <
      1024 * 1024
    ) {
      throw new Error(
        `ONNX 文件异常小：${Math.round(
          buf.byteLength / 1024
        )} KB。很可能模型损坏、下载不完整，或者并非真正 ONNX`
      );
    }

    // ------------------------------
    // 创建 ONNX session
    // ------------------------------

    try {
      this.session =
        await window.ort
          .InferenceSession
          .create(
            buf,
            {
              executionProviders: [
                'wasm',
              ],
            }
          );
    } catch (e) {
      throw new Error(
        [
          'ONNX Runtime 无法解析模型。',
          `模型大小：${(
            buf.byteLength /
            1024 /
            1024
          ).toFixed(2)} MB`,
          `content-type：${
            contentType ||
            'unknown'
          }`,
          `原始错误：${e.message}`,
        ].join(' ')
      );
    }

    console.info(
      '[detector] YOLO 初始化成功',
      {
        url: this.modelUrl,
        inputNames:
          this.session.inputNames,
        outputNames:
          this.session.outputNames,
      }
    );
  }

  async detect(frame) {
    if (!this.session) {
      return [];
    }

    const S =
      CONFIG.detect.inputSize;

    const src =
      frame.canvas;

    // ------------------------------
    // letterbox
    // ------------------------------

    const r =
      Math.min(
        S / src.width,
        S / src.height
      );

    const nw =
      src.width * r;

    const nh =
      src.height * r;

    const dx =
      (S - nw) / 2;

    const dy =
      (S - nh) / 2;

    const off =
      document.createElement(
        'canvas'
      );

    off.width = S;
    off.height = S;

    const ctx =
      off.getContext(
        '2d',
        {
          willReadFrequently: true,
        }
      );

    ctx.fillStyle =
      'rgb(114,114,114)';

    ctx.fillRect(
      0,
      0,
      S,
      S
    );

    ctx.drawImage(
      src,
      dx,
      dy,
      nw,
      nh
    );

    const img =
      ctx.getImageData(
        0,
        0,
        S,
        S
      ).data;

    // ------------------------------
    // RGBA → NCHW Float32
    // ------------------------------

    const plane =
      S * S;

    const data =
      new Float32Array(
        3 * plane
      );

    for (
      let i = 0,
        px = 0;
      px < plane;
      px++,
        i += 4
    ) {
      data[px] =
        img[i] / 255;

      data[
        plane + px
      ] =
        img[i + 1] /
        255;

      data[
        plane * 2 +
          px
      ] =
        img[i + 2] /
        255;
    }

    // ------------------------------
    // inference
    // ------------------------------

    const feeds = {};

    feeds[
      this.session
        .inputNames[0]
    ] =
      new window.ort.Tensor(
        'float32',
        data,
        [1, 3, S, S]
      );

    const out =
      await this.session.run(
        feeds
      );

    const t =
      out[
        this.session
          .outputNames[0]
      ];

    if (!t) {
      throw new Error(
        'YOLO 没有返回输出 Tensor'
      );
    }

    console.debug(
      '[detector] YOLO output dims:',
      t.dims
    );

    // ========================================================
    // YOLOv8 输出解析
    //
    // 常见：
    //
    // [1,84,8400]
    //   84 features
    //   8400 anchors
    //
    // 或：
    //
    // [1,8400,84]
    // ========================================================

    const dims =
      t.dims;

    if (
      !Array.isArray(
        dims
      ) ||
      dims.length < 2
    ) {
      throw new Error(
        `YOLO 输出维度异常：${JSON.stringify(
          dims
        )}`
      );
    }

    const a =
      dims[
        dims.length - 2
      ];

    const b =
      dims[
        dims.length - 1
      ];

    const d =
      t.data;

    let nAnchors;
    let nFeat;
    let get;

    // --------------------------------
    // [1,84,N]
    // --------------------------------

    if (a === 84) {
      nFeat = a;
      nAnchors = b;

      get =
        (ch, i) =>
          d[
            ch *
              nAnchors +
              i
          ];
    }

    // --------------------------------
    // [1,N,84]
    // --------------------------------

    else if (b === 84) {
      nAnchors = a;
      nFeat = b;

      get =
        (ch, i) =>
          d[
            i *
              nFeat +
              ch
          ];
    }

    else {
      throw new Error(
        `暂不支持 YOLO 输出形状：${JSON.stringify(
          dims
        )}。期望 [1,84,N] 或 [1,N,84]`
      );
    }

    // ------------------------------
    // decode
    // ------------------------------

    const raw = [];

    for (
      let i = 0;
      i < nAnchors;
      i++
    ) {
      let bestClassIndex =
        -1;

      let bestScore =
        0;

      // 0-3:
      // cx cy w h
      //
      // 4-83:
      // COCO 80 类

      for (
        let j = 4;
        j < nFeat;
        j++
      ) {
        const p =
          get(j, i);

        if (
          p >
          bestScore
        ) {
          bestScore =
            p;

          bestClassIndex =
            j - 4;
        }
      }

      if (
        bestScore <
        CONFIG.detect
          .scoreThresh
      ) {
        continue;
      }

      if (
        bestClassIndex <
          0 ||
        bestClassIndex >=
          COCO_CLASSES.length
      ) {
        continue;
      }

      const cx =
        get(0, i);

      const cy =
        get(1, i);

      const w =
        get(2, i);

      const h =
        get(3, i);

      // ------------------------------
      // letterbox inverse transform
      // ------------------------------

      const x0 =
        (
          cx -
          w / 2 -
          dx
        ) / r;

      const y0 =
        (
          cy -
          h / 2 -
          dy
        ) / r;

      const originalW =
        w / r;

      const originalH =
        h / r;

      const className =
        COCO_CLASSES[
          bestClassIndex
        ];

      // ======================================================
      // 万物模式只选“物体”
      // 排除拍摄者 / 孩子 / 家长本人
      // ======================================================

      if (
        className === 'person'
      ) {
        continue;
      }

      const label =
        COCO_ZH[
          className
        ] ||
        className ||
        '物体';

      raw.push({
        label,

        score:
          +bestScore.toFixed(
            3
          ),

        bbox:
          clampBox(
            [
              x0,
              y0,
              originalW,
              originalH,
            ],
            src.width,
            src.height
          ),
      });
    }

    const result =
      nms(
        raw,
        CONFIG.detect
          .iouThresh
      )
        .slice(
          0,
          CONFIG.detect
            .maxBoxes
        );

    console.debug(
      '[detector] YOLO detections:',
      result
    );

    return result;
  }
}

// ============================================================
// IOU / NMS
// ============================================================

export function iou(
  a,
  b
) {
  const x1 =
    Math.max(
      a[0],
      b[0]
    );

  const y1 =
    Math.max(
      a[1],
      b[1]
    );

  const x2 =
    Math.min(
      a[0] +
        a[2],
      b[0] +
        b[2]
    );

  const y2 =
    Math.min(
      a[1] +
        a[3],
      b[1] +
        b[3]
    );

  const inter =
    Math.max(
      0,
      x2 - x1
    ) *
    Math.max(
      0,
      y2 - y1
    );

  const uni =
    a[2] *
      a[3] +
    b[2] *
      b[3] -
    inter;

  return (
    uni <= 0
      ? 0
      : inter / uni
  );
}

export function nms(
  boxes,
  thr = 0.45
) {
  const sorted =
    [...boxes].sort(
      (a, b) =>
        b.score -
        a.score
    );

  const keep = [];

  for (
    const b of sorted
  ) {
    if (
      keep.every(
        (k) =>
          iou(
            k.bbox,
            b.bbox
          ) < thr
      )
    ) {
      keep.push(b);
    }
  }

  return keep;
}

// ============================================================
// 2. SaliencyDetector
//
// 注意：
// 这个检测器只识别颜色区域。
// 它不能识别真实物体语义。
// 因此只有用户明确选择 saliency 时才能使用。
// ============================================================

export class SaliencyDetector {
  constructor() {
    this.name =
      'saliency';

    this.GW =
      96;
  }

  async init() {}

  async detect(frame) {
    const src =
      frame.canvas;

    const gw =
      this.GW;

    const gh =
      Math.max(
        24,
        Math.round(
          (
            gw *
            src.height
          ) /
            src.width
        )
      );

    const off =
      document.createElement(
        'canvas'
      );

    off.width =
      gw;

    off.height =
      gh;

    const ctx =
      off.getContext(
        '2d',
        {
          willReadFrequently: true,
        }
      );

    ctx.drawImage(
      src,
      0,
      0,
      gw,
      gh
    );

    const d =
      ctx.getImageData(
        0,
        0,
        gw,
        gh
      ).data;

    const mask =
      new Uint8Array(
        gw * gh
      );

    const hues =
      new Float32Array(
        gw * gh
      );

    for (
      let i = 0;
      i < gw * gh;
      i++
    ) {
      const [
        h,
        s,
        v,
      ] =
        rgb2hsv(
          d[i * 4],
          d[
            i * 4 + 1
          ],
          d[
            i * 4 + 2
          ]
        );

      if (
        s > 0.4 &&
        v > 0.35
      ) {
        mask[i] =
          1;

        hues[i] =
          h;
      }
    }

    const seen =
      new Uint8Array(
        gw * gh
      );

    const blobs = [];

    for (
      let i = 0;
      i < gw * gh;
      i++
    ) {
      if (
        !mask[i] ||
        seen[i]
      ) {
        continue;
      }

      const q = [i];

      seen[i] = 1;

      let minX = gw;
      let minY = gh;

      let maxX = 0;
      let maxY = 0;

      let count = 0;

      let hx = 0;
      let hy = 0;

      while (
        q.length
      ) {
        const cur =
          q.pop();

        const cx =
          cur % gw;

        const cy =
          (
            cur / gw
          ) | 0;

        count++;

        hx += cx;
        hy += cy;

        if (
          cx < minX
        ) {
          minX =
            cx;
        }

        if (
          cy < minY
        ) {
          minY =
            cy;
        }

        if (
          cx > maxX
        ) {
          maxX =
            cx;
        }

        if (
          cy > maxY
        ) {
          maxY =
            cy;
        }

        for (
          const [
            nx,
            ny,
          ] of [
            [
              cx - 1,
              cy,
            ],
            [
              cx + 1,
              cy,
            ],
            [
              cx,
              cy - 1,
            ],
            [
              cx,
              cy + 1,
            ],
          ]
        ) {
          if (
            nx < 0 ||
            ny < 0 ||
            nx >= gw ||
            ny >= gh
          ) {
            continue;
          }

          const ni =
            ny * gw +
            nx;

          if (
            mask[ni] &&
            !seen[ni]
          ) {
            seen[ni] =
              1;

            q.push(
              ni
            );
          }
        }
      }

      if (
        count >=
        gw *
          gh *
          0.008
      ) {
        const centerX =
          Math.round(
            hx / count
          );

        const centerY =
          Math.round(
            hy / count
          );

        const hueIndex =
          centerY *
            gw +
          centerX;

        const avgH =
          hues[
            hueIndex
          ] || 0;

        blobs.push({
          label:
            `${hueName(
              avgH
            )}东西`,

          score:
            +Math.min(
              0.9,
              (
                count /
                (
                  gw *
                  gh
                )
              ) *
                3
            ).toFixed(
              2
            ),

          bbox:
            clampBox(
              [
                (
                  minX /
                  gw
                ) *
                  src.width,

                (
                  minY /
                  gh
                ) *
                  src.height,

                (
                  (
                    maxX -
                    minX +
                    1
                  ) /
                  gw
                ) *
                  src.width,

                (
                  (
                    maxY -
                    minY +
                    1
                  ) /
                  gh
                ) *
                  src.height,
              ],
              src.width,
              src.height
            ),
        });
      }
    }

    return nms(
      blobs,
      0.3
    )
      .sort(
        (a, b) =>
          b.score -
          a.score
      )
      .slice(
        0,
        CONFIG.detect
          .maxBoxes
      );
  }
}

function rgb2hsv(
  r,
  g,
  b
) {
  r /= 255;
  g /= 255;
  b /= 255;

  const max =
    Math.max(
      r,
      g,
      b
    );

  const min =
    Math.min(
      r,
      g,
      b
    );

  const v =
    max;

  const s =
    max === 0
      ? 0
      : 1 -
        min /
          max;

  let h = 0;

  const d =
    max -
    min;

  if (d > 0) {
    if (
      max === r
    ) {
      h =
        60 *
        (
          (
            (
              g -
              b
            ) /
            d
          ) %
          6
        );
    } else if (
      max === g
    ) {
      h =
        60 *
        (
          (
            b -
            r
          ) /
            d +
          2
        );
    } else {
      h =
        60 *
        (
          (
            r -
            g
          ) /
            d +
          4
        );
    }
  }

  if (
    h < 0
  ) {
    h += 360;
  }

  return [
    h,
    s,
    v,
  ];
}

// ============================================================
// 3. StaticSceneDetector
// ============================================================

export class StaticSceneDetector {
  constructor(scene) {
    this.name =
      'static';

    this.scene =
      scene;
  }

  async init() {}

  async detect() {
    return this.scene.objects.map(
      (o) => ({
        label:
          o.label,

        score:
          0.92,

        bbox:
          clampBox(
            o.bbox,
            this.scene
              .canvas
              .width,
            this.scene
              .canvas
              .height
          ),
      })
    );
  }
}

// ============================================================
// Provider 选择
//
// 关键逻辑：
//
// demo:
//   static
//
// camera + auto:
//   YOLO
//
// camera + yolo:
//   YOLO
//
// saliency:
//   只有显式选择才启用
//
// YOLO 失败：
//   直接报错
//
// 不再：
//   YOLO失败 → “橙色的东西”
// ============================================================

export async function createDetector(
  preference,
  scene
) {
  // --------------------------------
  // 演示场景
  // --------------------------------

  if (
    preference ===
      'static' ||
    (
      preference ===
        'auto' &&
      scene
    )
  ) {
    const d =
      new StaticSceneDetector(
        scene
      );

    await d.init();

    console.info(
      '[detector] 使用静态演示检测器'
    );

    return d;
  }

  // --------------------------------
  // 颜色显著性
  //
  // 只能显式选择
  // --------------------------------

  if (
    preference ===
    'saliency'
  ) {
    const s =
      new SaliencyDetector();

    await s.init();

    console.warn(
      '[detector] 当前使用 SaliencyDetector，它只能检测颜色区域，不能识别真实物体'
    );

    return s;
  }

  // --------------------------------
  // YOLO
  // --------------------------------

  if (
    preference ===
      'auto' ||
    preference ===
      'yolo'
  ) {
    const d =
      new YoloDetector();

    try {
      await d.init();

      console.info(
        '[detector] 使用 YOLO 真实物体检测'
      );

      return d;
    } catch (e) {
      console.error(
        '[detector] YOLO 初始化失败：',
        e
      );

      throw new Error(
        [
          '真实物体检测器不可用。',
          e.message,
          '已禁止自动降级为颜色伪识别，因此不会再播报“橙色的东西”。',
        ].join(' ')
      );
    }
  }

  throw new Error(
    `未知检测器：${preference}`
  );
}
