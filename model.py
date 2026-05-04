import os
import cv2
import numpy as np
import pickle
import face_recognition
from sklearn.ensemble import RandomForestClassifier

MODEL_PATH = "model.pkl"


def extract_embedding_for_image(input_data):
    """
    Extract 128-dim face embedding using dlib (via face_recognition library).
    """
    try:
        # Handle file stream or numpy image
        if hasattr(input_data, "read"):
            file_bytes = np.frombuffer(input_data.read(), np.uint8)
            img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        else:
            img_bgr = input_data

        if img_bgr is None:
            return None

        # Convert to RGB
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Detect faces
        face_locations = face_recognition.face_locations(img_rgb, model="hog")
        if not face_locations:
            return None

        # Get embedding for first face
        encodings = face_recognition.face_encodings(img_rgb, face_locations)
        if not encodings:
            return None

        return encodings[0]

    except Exception as e:
        print(f"Embedding error: {e}")
        return None


def extract_embeddings_for_image(input_data):
    """
    Extract embeddings for ALL faces in image.
    """
    try:
        if hasattr(input_data, "read"):
            file_bytes = np.frombuffer(input_data.read(), np.uint8)
            img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        else:
            img_bgr = input_data

        if img_bgr is None:
            return []

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(img_rgb, model="hog")
        if not face_locations:
            return []

        encodings = face_recognition.face_encodings(img_rgb, face_locations)
        return encodings

    except Exception as e:
        print(f"Embedding error: {e}")
        return []


def load_model_if_exists():
    if not os.path.exists(MODEL_PATH):
        return None

    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict_with_model(clf, emb, threshold=0.55):
    proba = clf.predict_proba([emb])[0]
    idx = np.argmax(proba)
    confidence = float(proba[idx])

    print(f"DEBUG: Predicted {clf.classes_[idx]} with confidence {confidence:.3f}")

    if confidence < threshold:
        return "Unknown", confidence

    return clf.classes_[idx], confidence


def train_model_background(dataset_dir, progress_callback=None):
    X, y = [], []

    student_dirs = [
        sid for sid in os.listdir(dataset_dir)
        if os.path.isdir(os.path.join(dataset_dir, sid))
    ]

    total = len(student_dirs)

    if total == 0:
        if progress_callback:
            progress_callback(0, "No students found")
        return

    for i, sid in enumerate(student_dirs):
        folder = os.path.join(dataset_dir, sid)

        for file in os.listdir(folder):
            if not file.lower().endswith((".jpg", ".png", ".jpeg")):
                continue

            img_path = os.path.join(folder, file)
            img_bgr = cv2.imread(img_path)

            if img_bgr is None:
                continue

            emb = extract_embedding_for_image(img_bgr)

            if emb is not None:
                X.append(emb)
                y.append(int(sid))

        if progress_callback:
            progress = int((i + 1) / total * 90)
            progress_callback(progress, f"Processing student {i+1}/{total}")

    # ⚠️ FIX: This was logically wrong in your code
    if not X:
        if progress_callback:
            progress_callback(0, "No face data found")
        return

    print(f"Training on {len(X)} samples for {len(set(y))} students...")

    clf = RandomForestClassifier(n_estimators=300, random_state=42)
    clf.fit(np.array(X), np.array(y))

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)

    if progress_callback:
        progress_callback(100, "Training complete")

    print("✔ Model trained and saved!")