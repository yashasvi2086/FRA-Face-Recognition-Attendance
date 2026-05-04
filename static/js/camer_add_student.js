// ELEMENTS
const startCaptureBtn = document.getElementById("startCaptureBtn");
const addStudentBtn = document.getElementById("addStudentBtn");
const video = document.getElementById("video");
const captureStatus = document.getElementById("captureStatus");
const progressBar = document.getElementById("progressBar");
const formEl = document.getElementById("studentForm");

let student_id = null;
let captured = 0;
const maxImages = 50;
let images = [];
let stream = null;
let capturing = false;

/* ===============================
SAVE STUDENT INFO
================================ */
formEl.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fd = new FormData(e.target);

    try {
        const res = await fetch("/add_student", {
            method: "POST",
            body: fd
        });

        if (!res.ok) {
            alert("Failed to save student info");
            return;
        }

        const data = await res.json();
        student_id = data.student_id;

        alert("Student info saved. Click Start Capture.");
        startCaptureBtn.disabled = false;

    } catch (err) {
        console.error(err);
        alert("Server error while saving student");
    }
});

/* ===============================
START CAMERA
================================ */
startCaptureBtn.addEventListener("click", async () => {
    if (!student_id) {
        alert("Save student info first");
        return;
    }

    startCaptureBtn.disabled = true;

    // Reset state
    captured = 0;
    images = [];
    capturing = true;

    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 }
        });

        video.srcObject = stream;

        // Wait for video to be ready
        await new Promise(resolve => {
            video.onloadedmetadata = () => resolve();
        });

        await video.play();

        captureImagesLoop();

    } catch (err) {
        console.error(err);
        alert("Camera access error: " + err.message);
        startCaptureBtn.disabled = false;
    }
});

/* ===============================
CAPTURE IMAGES LOOP
================================ */
async function captureImagesLoop() {

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    while (capturing && captured < maxImages) {

        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const blob = await new Promise(resolve =>
            canvas.toBlob(resolve, "image/jpeg", 0.9)
        );

        if (blob) {
            images.push(blob);
            captured++;
        }

        captureStatus.innerText = `Captured ${captured} / ${maxImages}`;

        // Progress bar fix (width instead of value)
        if (progressBar) {
            progressBar.style.width = (captured / maxImages * 100) + "%";
        }

        await new Promise(r => setTimeout(r, 250));
    }

    capturing = false;

    captureStatus.innerText = "Uploading images...";

    const form = new FormData();
    form.append("student_id", student_id);

    images.forEach((img, i) => {
        form.append("images[]", img, `img_${i}.jpg`);
    });

    try {
        const resp = await fetch("/upload_face", {
            method: "POST",
            body: form
        });

        if (resp.ok) {
            captureStatus.innerText = "Capture completed ✔ Starting Training...";
            
            // Auto train the model
            try {
                await fetch("/train_model");
                captureStatus.innerText = "Capture & Training Initiated ✔";
            } catch (e) {
                console.error("Auto train failed", e);
            }
            
            addStudentBtn.disabled = false;
        } else {
            alert("Upload failed");
        }

    } catch (err) {
        console.error(err);
        alert("Upload error");
    }

    // Stop camera
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
        stream = null;
    }
}

/* ===============================
FINISH
================================ */
addStudentBtn.addEventListener("click", () => {
    window.location.href = "/";
});