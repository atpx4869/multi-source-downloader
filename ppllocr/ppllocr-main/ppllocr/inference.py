import os
import cv2
import numpy as np
import onnxruntime as ort
import string

# 字符集 (必须与训练一致)
SPECIFIC_SYMBOLS = "/*%@#"
CHARACTERS = string.digits + string.ascii_letters + SPECIFIC_SYMBOLS

class OCR:
    def __init__(self, model_path=None, use_gpu=False):
        # 1. 如果用户没传路径，自动加载包内的默认模型
        if model_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 注意：这里假设文件名是 ppllocr_v1.onnx，如果你的文件名不同请修改
            model_path = os.path.join(current_dir, "assets", "ppllocr_v1.onnx")
        
        if not os.path.exists(model_path):
            # 尝试查找旧文件名兼容
            fallback_path = os.path.join(current_dir, "assets", "yolo_ocr.onnx")
            if os.path.exists(fallback_path):
                model_path = fallback_path
            else:
                raise FileNotFoundError(f"Model file not found: {model_path}")

        self.class_names = CHARACTERS
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if use_gpu else ['CPUExecutionProvider']
        
        try:
            self.session = ort.InferenceSession(model_path, providers=providers)
        except Exception:
            # 回退到 CPU
            self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])

        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.img_size = (512, 512) # 训练时的 imgsz

    def letterbox(self, im, new_shape=(512, 512), color=(114, 114, 114)):
        shape = im.shape[:2]
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
        dw /= 2; dh /= 2
        
        if shape[::-1] != new_unpad:
            im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
            
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return im, r, (dw, dh)

    def preprocess(self, img_src):
        image, ratio, (dw, dh) = self.letterbox(img_src, new_shape=self.img_size)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = image.astype(np.float32) / 255.0
        image = image.transpose(2, 0, 1)
        image = np.expand_dims(image, axis=0)
        return image, {'ratio': ratio, 'dw': dw, 'dh': dh}

    def xywh2xyxy(self, x):
        y = np.copy(x)
        y[:, 0] = x[:, 0] - x[:, 2] / 2
        y[:, 1] = x[:, 1] - x[:, 3] / 2
        y[:, 2] = x[:, 0] + x[:, 2] / 2
        y[:, 3] = x[:, 1] + x[:, 3] / 2
        return y

    def nms_numpy(self, boxes, scores, iou_threshold):
        if len(boxes) == 0: return []
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            inds = np.where(ovr <= iou_threshold)[0]
            order = order[inds + 1]
        return keep

    def _run_inference(self, input_source, conf=0.25, iou=0.45):
        """内部核心推理方法"""
        img = None
        if isinstance(input_source, str):
            if os.path.exists(input_source): img = cv2.imread(input_source)
        elif isinstance(input_source, bytes):
            nparr = np.frombuffer(input_source, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(input_source, np.ndarray):
            img = input_source
            
        if img is None: return "", []

        input_tensor, meta = self.preprocess(img)
        outputs = self.session.run([self.output_name], {self.input_name: input_tensor})
        
        predictions = np.squeeze(outputs[0]).T 
        scores = np.max(predictions[:, 4:], axis=1)
        keep_mask = scores > conf
        predictions = predictions[keep_mask]
        scores = scores[keep_mask]
        
        if len(predictions) == 0: return "", []
        
        class_ids = np.argmax(predictions[:, 4:], axis=1)
        boxes = self.xywh2xyxy(predictions[:, :4])
        
        indices = self.nms_numpy(boxes, scores, iou)
        final_boxes = boxes[indices]
        final_scores = scores[indices]
        final_ids = class_ids[indices]
        
        # 坐标还原
        final_boxes[:, 0] -= meta['dw']; final_boxes[:, 2] -= meta['dw']
        final_boxes[:, 1] -= meta['dh']; final_boxes[:, 3] -= meta['dh']
        final_boxes /= meta['ratio']
        
        # 排序
        sorted_indices = np.argsort(final_boxes[:, 0])
        
        result_text = []
        details = []
        for idx in sorted_indices:
            cid = final_ids[idx]
            if cid < len(self.class_names):
                char = self.class_names[cid]
                result_text.append(char)
                details.append({
                    "char": char,
                    "conf": float(final_scores[idx]),
                    "box": final_boxes[idx].tolist()
                })
        
        return "".join(result_text), details

    def classification(self, input_source, conf=0.25, iou=0.45):
        """
        直接返回识别的内容字符串
        """
        text, _ = self._run_inference(input_source, conf, iou)
        return text

    def classification_box(self, input_source, conf=0.25, iou=0.45):
        """
        直接返回识别的内容字符串和检测详细信息
        :return: (text, details) 
                 details 为列表，每项包含 {'char': 字符, 'conf': 置信度, 'box': [x1, y1, x2, y2]}
        """
        return self._run_inference(input_source, conf, iou)

    def predict(self, input_source, conf=0.25, iou=0.45):
        """
        (保留接口兼容性) 同 classification_box
        """
        return self.classification_box(input_source, conf, iou)