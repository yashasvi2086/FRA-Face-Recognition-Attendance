/* ===============================
ELEMENTS
================================ */
const markVideo = document.getElementById("markVideo");
const startMarkBtn = document.getElementById("startMarkBtn");
const stopMarkBtn = document.getElementById("stopMarkBtn");
const markStatus = document.getElementById("markStatus");
const recognizedList = document.getElementById("recognizedList");

let markStream = null;
let markInterval = null;
let recognizedIds = new Set();

/* ===============================
STOP MARKING
================================ */
stopMarkBtn.addEventListener("click", () => {
    if (markInterval) {
        clearInterval(markInterval);
        markInterval = null;
    }

    if (markStream) {
        markStream.getTracks().forEach(t => t.stop());
        markStream = null;
    }

    startMarkBtn.disabled = false;
    stopMarkBtn.disabled = true;
    markStatus.innerText = "Stopped";
});

/* ===============================
CAPTURE + RECOGNIZE
================================ */
async function captureAndRecognize() {

    // Ensure video is ready
    if (!markVideo.videoWidth || !markVideo.videoHeight) return;

    const canvas = document.createElement("canvas");
    canvas.width = markVideo.videoWidth;
    canvas.height = markVideo.videoHeight;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(markVideo, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise(resolve =>
        canvas.toBlob(resolve, "image/jpeg", 0.85)
    );

    if (!blob) return; // safety

    const fd = new FormData();
    fd.append("image", blob, "snap.jpg");

    try {
        const res = await fetch("/recognize_face", {
            method: "POST",
            body: fd
        });

        if (!res.ok) {
            markStatus.innerText = "Server error during recognition";
            return;
        }

        const j = await res.json();

        if (j.recognized) {
            markStatus.innerText =
                `Recognized: ${j.name} (${Math.round(j.confidence * 100)}%)`;

            // Avoid duplicate entries
            if (!recognizedIds.has(j.student_id)) {
                recognizedIds.add(j.student_id);

                const li = document.createElement("li");
                li.className = "list-group-item";
                li.innerText = `${j.name} - ${new Date().toLocaleTimeString()}`;

                recognizedList.prepend(li);
            }

        } else {
            markStatus.innerText = j.error
                ? `Not recognized: ${j.error}`
                : "No match found";
        }

    } catch (err) {
        console.error(err);
        markStatus.innerText = "Recognition failed";
    }
}

/* ===============================
START MARKING
================================ */
startMarkBtn.addEventListener("click", async () => {
    try {
        markStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: false
        });

        markVideo.srcObject = markStream;

        // Wait for video readiness
        await new Promise(resolve => {
            markVideo.onloadedmetadata = () => resolve();
        });

        await markVideo.play();

        startMarkBtn.disabled = true;
        stopMarkBtn.disabled = false;

        markStatus.innerText = "Camera started. Recognizing...";

        recognizedIds.clear();
        recognizedList.innerHTML = "";

        // Prevent duplicate intervals
        if (markInterval) clearInterval(markInterval);

        markInterval = setInterval(captureAndRecognize, 2000);

    } catch (err) {
        console.error(err);
        markStatus.innerText = "Unable to access camera";
        alert("Camera permission denied or unavailable");
    }
});