from flask import Flask, request, jsonify
from flask_cors import cross_origin
import numpy as np
import cv2
import tensorflow as tf
from utils.detect_mask import preprocess_image, detect_and_crop_face

app = Flask(__name__)

interpreter = tf.lite.Interpreter(model_path='./models/model_quant.tflite')
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

def tflite_predict(input_img):
    input_img = input_img.astype(np.float32).copy()
    interpreter.set_tensor(input_details[0]['index'], input_img)
    interpreter.invoke()
    output = np.array(interpreter.get_tensor(output_details[0]['index'])).copy()
    return output

origins = ["https://ku-face-mask-frontend.vercel.app"]

@app.get("/")
def index():
    return "Hello World!", 200

@app.post('/api/mask-detection')
@cross_origin(origins=origins, methods=["POST"], allow_headers=["Content-Type"])
def detect_mask():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({'error': 'Cannot decode image'}), 400

        # ตรวจจับใบหน้าและเก็บตำแหน่งกรอบ
        face_img, box = detect_and_crop_face(img)
        if face_img is None:
            return jsonify({'error': 'No face detected'}), 200

        input_img = preprocess_image(face_img)
        prediction = tflite_predict(input_img)
        prediction = prediction.copy()

        # ปรับชื่อ class ให้ตรงกับที่เทรน
        class_labels = ["No Mask", "Mask", "No_Mask."]

        pred_idx = int(np.argmax(prediction[0]))
        confidence = float(np.max(prediction[0]))
        label = class_labels[pred_idx]

        # กำหนดสีตาม label
        if label == "Mask":
            color = "green"
        else:
            color = "red"

        result = {
            "label": label,
            "confidence": confidence,
            "box": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
            "color": color
        }
        return jsonify({"results": [result]})
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "ไม่พบใบหน้า"}), 200
