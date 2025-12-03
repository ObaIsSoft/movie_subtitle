document.addEventListener('DOMContentLoaded', () => {
    console.log("Audio Visualizer Script Loaded (Hybrid Version)");
    const micButton = document.getElementById('mic-button');
    const audioOverlay = document.getElementById('audio-overlay');
    const closeOverlayBtn = document.getElementById('close-overlay');
    const canvas = document.getElementById('visualizer-canvas');
    const canvasCtx = canvas.getContext('2d');
    const statusText = document.getElementById('recording-status');
    const transcriptDiv = document.getElementById('live-transcript');
    const searchInput = document.getElementById('search-input');
    const searchForm = document.getElementById('search-form');

    // State Variables
    let audioContext = null;
    let analyser = null;
    let dataArray = null;
    let source = null;
    let stream = null;
    let animationId = null;
    let isRecording = false;

    // Strategy Variables
    let recognition = null; // For Web Speech API
    let mediaRecorder = null; // For Fallback
    let audioChunks = []; // For Fallback

    // Feature Detection
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const useWebSpeech = !!SpeechRecognition;

    console.log("Using Web Speech API:", useWebSpeech);

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
        if (isRecording) return; // Prevent double clicks

        try {
            // 1. Start Audio Stream (Common for both strategies)
            stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            // UI Updates
            audioOverlay.classList.add('active');
            statusText.innerText = useWebSpeech ? "Listening..." : "Recording...";
            transcriptDiv.innerText = "";
            isRecording = true;

            // 2. Start Visualizer (Common)
            setupVisualizer(stream);
            drawVisualizer();

            // 3. Start Recording Strategy
            if (useWebSpeech) {
                startWebSpeechStrategy();
            } else {
                startMediaRecorderStrategy();
            }

        } catch (err) {
            console.error('Error accessing microphone:', err);
            alert('Could not access microphone. Please allow permissions.');
            stopRecordingUI();
        }
    }

    function setupVisualizer(stream) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;

        source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        const bufferLength = analyser.frequencyBinCount;
        dataArray = new Uint8Array(bufferLength);
    }

    // --- STRATEGY 1: WEB SPEECH API (Real-time) ---
    function startWebSpeechStrategy() {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => console.log("Speech recognition started");

        recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }
            transcriptDiv.innerText = finalTranscript || interimTranscript;

            if (finalTranscript) {
                searchInput.value = finalTranscript;
            }
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error", event.error);
            if (event.error === 'no-speech') {
                statusText.innerText = "No speech detected.";
            } else {
                statusText.innerText = "Error: " + event.error;
            }
        };

        recognition.onend = () => {
            console.log("Speech recognition ended");
            if (isRecording) {
                if (searchInput.value && searchInput.value.trim() !== "") {
                    stopRecordingUI();
                    searchForm.submit();
                } else {
                    stopRecording();
                    statusText.innerText = "Tap mic to try again";
                }
            }
        };

        recognition.start();
    }

    // --- STRATEGY 2: MEDIA RECORDER (Fallback) ---
    function startMediaRecorderStrategy() {
        const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' :
            MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '';

        if (!mimeType) {
            alert('Audio recording is not supported on this browser.');
            stopRecordingUI();
            return;
        }

        mediaRecorder = new MediaRecorder(stream, { mimeType });
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            if (audioChunks.length > 0) {
                const audioBlob = new Blob(audioChunks, { type: mimeType });
                await sendAudioToBackend(audioBlob, mimeType);
            }
        };

        mediaRecorder.start();

        // Auto-stop fallback after 5 seconds since it doesn't have smart endpointing
        setTimeout(() => {
            if (isRecording) {
                stopRecording();
                statusText.innerText = "Processing...";
            }
        }, 5000);
    }

    async function sendAudioToBackend(audioBlob, mimeType) {
        const formData = new FormData();
        const extension = mimeType.includes('mp4') ? 'mp4' : 'webm';
        formData.append('audio', audioBlob, `recording.${extension}`);

        try {
            const response = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.text) {
                stopRecordingUI();
                searchInput.value = data.text;
                searchForm.submit();
            } else {
                statusText.innerText = "Try Again";
            }
        } catch (error) {
            console.error('Transcription failed:', error);
            statusText.innerText = "Error";
        }
    }

    // --- CLEANUP ---
    function stopRecording() {
        if (!isRecording) return;
        isRecording = false;

        // Stop Web Speech
        if (recognition) {
            recognition.stop();
            recognition = null;
        }

        // Stop MediaRecorder
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            mediaRecorder = null;
        }

        // Stop Stream Tracks
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }

        // Close Audio Context
        if (audioContext) {
            audioContext.close().catch(e => console.error("Error closing context:", e));
            audioContext = null;
        }

        cancelAnimationFrame(animationId);
    }

    function stopRecordingUI() {
        stopRecording();
        audioOverlay.classList.remove('active');
    }

    // --- VISUALIZER ---
    function drawVisualizer() {
        if (!isRecording) return;
        animationId = requestAnimationFrame(drawVisualizer);

        analyser.getByteTimeDomainData(dataArray);

        canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
        canvasCtx.lineWidth = 3;

        const gradient = canvasCtx.createLinearGradient(0, 0, canvas.width, 0);
        gradient.addColorStop(0, '#00f2ff');
        gradient.addColorStop(0.5, '#ffffff');
        gradient.addColorStop(1, '#ff0055');

        canvasCtx.strokeStyle = gradient;
        canvasCtx.beginPath();

        const sliceWidth = canvas.width * 1.0 / dataArray.length;
        let x = 0;

        for (let i = 0; i < dataArray.length; i++) {
            const v = dataArray[i] / 128.0;
            const y = (v * canvas.height) / 2;

            if (i === 0) canvasCtx.moveTo(x, y);
            else canvasCtx.lineTo(x, y);

            x += sliceWidth;
        }
        canvasCtx.lineTo(canvas.width, canvas.height / 2);
        canvasCtx.stroke();

        canvasCtx.beginPath();
        x = 0;
        for (let i = 0; i < dataArray.length; i++) {
            const v = dataArray[i] / 128.0;
            const y = canvas.height - (v * canvas.height) / 2;

            if (i === 0) canvasCtx.moveTo(x, y);
            else canvasCtx.lineTo(x, y);
            x += sliceWidth;
        }
        canvasCtx.stroke();
    }
});
