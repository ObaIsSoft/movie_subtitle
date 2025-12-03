document.addEventListener('DOMContentLoaded', () => {
    const micButton = document.getElementById('mic-button');
    const audioOverlay = document.getElementById('audio-overlay');
    const closeOverlayBtn = document.getElementById('close-overlay');
    const canvas = document.getElementById('visualizer-canvas');
    const canvasCtx = canvas.getContext('2d');
    const statusText = document.getElementById('recording-status');
    const searchInput = document.getElementById('search-input');
    const searchForm = document.getElementById('search-form');

    let audioContext;
    let analyser;
    let dataArray;
    let source;
    let mediaRecorder;
    let audioChunks = [];
    let animationId;
    let isRecording = false;

    // Initialize Canvas
    function resizeCanvas() {
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    micButton.addEventListener('click', startRecording);
    closeOverlayBtn.addEventListener('click', stopRecordingUI);

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // UI Updates
            audioOverlay.classList.add('active');
            statusText.innerText = "Listening...";
            isRecording = true;

            // Audio Context Setup
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;

            source = audioContext.createMediaStreamSource(stream);
            source.connect(analyser);

            const bufferLength = analyser.frequencyBinCount;
            dataArray = new Uint8Array(bufferLength);

            // MediaRecorder Setup
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                await sendAudioToBackend(audioBlob);

                // Cleanup tracks
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            drawVisualizer();

            // Auto-stop after 5 seconds of silence or max duration (simple timeout for now)
            // For better UX, we could detect silence, but a 5s limit is safe for quotes.
            setTimeout(() => {
                if (isRecording) stopRecording();
            }, 5000);

        } catch (err) {
            console.error('Error accessing microphone:', err);
            alert('Could not access microphone. Please allow permissions.');
        }
    }

    function stopRecording() {
        if (!isRecording) return;
        isRecording = false;
        statusText.innerText = "Processing...";
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        cancelAnimationFrame(animationId);
    }

    function stopRecordingUI() {
        stopRecording();
        audioOverlay.classList.remove('active');
    }

    async function sendAudioToBackend(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        try {
            const response = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.text) {
                audioOverlay.classList.remove('active');
                searchInput.value = data.text;
                searchForm.submit(); // Auto-submit
            } else {
                statusText.innerText = "Try Again";
                setTimeout(() => audioOverlay.classList.remove('active'), 1500);
            }
        } catch (error) {
            console.error('Transcription failed:', error);
            statusText.innerText = "Error";
            setTimeout(() => audioOverlay.classList.remove('active'), 1500);
        }
    }

    // --- PULSATING WAVEFORM ANIMATION ---
    // Inspired by Siri / Voice assistants
    function drawVisualizer() {
        if (!isRecording) return;
        animationId = requestAnimationFrame(drawVisualizer);

        analyser.getByteTimeDomainData(dataArray);

        canvasCtx.fillStyle = 'rgba(0, 0, 0, 0.2)'; // Fade effect
        canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

        canvasCtx.lineWidth = 3;

        // Create gradient
        const gradient = canvasCtx.createLinearGradient(0, 0, canvas.width, 0);
        gradient.addColorStop(0, '#00f2ff'); // Cyan
        gradient.addColorStop(0.5, '#ffffff'); // White center
        gradient.addColorStop(1, '#ff0055'); // Pink/Red

        canvasCtx.strokeStyle = gradient;
        canvasCtx.beginPath();

        const sliceWidth = canvas.width * 1.0 / dataArray.length;
        let x = 0;

        for (let i = 0; i < dataArray.length; i++) {
            const v = dataArray[i] / 128.0; // Normalize 0-2 (1 is center)
            const y = (v * canvas.height) / 2;

            if (i === 0) {
                canvasCtx.moveTo(x, y);
            } else {
                canvasCtx.lineTo(x, y);
            }

            x += sliceWidth;
        }

        canvasCtx.lineTo(canvas.width, canvas.height / 2);
        canvasCtx.stroke();

        // Add a second mirrored line for "pulsating" effect
        canvasCtx.beginPath();
        x = 0;
        for (let i = 0; i < dataArray.length; i++) {
            const v = dataArray[i] / 128.0;
            // Invert the wave slightly for a "DNA" look
            const y = canvas.height - (v * canvas.height) / 2;

            if (i === 0) {
                canvasCtx.moveTo(x, y);
            } else {
                canvasCtx.lineTo(x, y);
            }
            x += sliceWidth;
        }
        canvasCtx.stroke();
    }
});
