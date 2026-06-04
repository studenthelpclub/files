(function() {
    document.addEventListener("DOMContentLoaded", function() {
        
        const imageInput = document.getElementById('imageInput');
        const settingsArea = document.getElementById('settingsArea');
        const resizeBtn = document.getElementById('resizeBtn');
        const resultArea = document.getElementById('resultArea');
        const finalImageSize = document.getElementById('finalImageSize');
        const downloadBtn = document.getElementById('downloadBtn');
        const targetKbInput = document.getElementById('targetKb');
        const targetWidthInput = document.getElementById('targetWidth');
        const targetHeightInput = document.getElementById('targetHeight');
        const cropperContainer = document.getElementById('cropperContainer');
        const cropperImage = document.getElementById('cropperImage');
        const finalPreview = document.getElementById('finalPreview');
        const statusText = document.getElementById('statusText');

        let globalResizedBlob = null;
        let cropperInstance = null;

        // --- 1. SELECTION & HEIC STATUS MESSAGE ---
        imageInput.addEventListener('change', async function(e) {
            if (e.target.files && e.target.files[0]) {
                let file = e.target.files[0];
                const fileName = file.name.toLowerCase();
                
                // Default status
                if (statusText) statusText.innerHTML = `<i class="fas fa-sync fa-spin"></i> Reading: ${file.name}`;

                // HEIC Conversion Status
                if (fileName.endsWith(".heic") || file.type === "image/heic" || file.type === "") {
                    if (statusText) {
                        statusText.innerHTML = `<b style="color: #0d6efd;"><i class="fas fa-magic fa-spin"></i> HEIC to JPG Converting... Please wait</b>`;
                    }
                    
                    try {
                        const convertedResult = await heic2any({ 
                            blob: file, 
                            toType: "image/jpeg",
                            quality: 0.7 
                        });

                        const blob = Array.isArray(convertedResult) ? convertedResult[0] : convertedResult;
                        file = new File([blob], file.name.split('.')[0] + ".jpg", { type: "image/jpeg" });
                        
                        if (statusText) statusText.innerHTML = `<i class="fas fa-check-circle" style="color:green;"></i> HEIC Ready: ${file.name}`;
                    } catch (err) {
                        if (statusText) statusText.innerHTML = `<b style="color:red;">HEIC Conversion Failed!</b>`;
                        return;
                    }
                } else {
                    if (statusText) statusText.innerHTML = `<i class="fas fa-image"></i> Selected: ${file.name}`;
                }

                handleFile(file);
            }
        });

        function handleFile(file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                if (cropperInstance) { cropperInstance.destroy(); }
                
                cropperImage.src = e.target.result;
                settingsArea.style.display = 'block';
                cropperContainer.style.display = 'block';
                resultArea.style.display = 'none';

                cropperInstance = new Cropper(cropperImage, {
                    aspectRatio: NaN,
                    viewMode: 1,
                    autoCropArea: 0.9,
                    responsive: true,
                    checkOrientation: true
                });
                
                setTimeout(() => {
                    settingsArea.scrollIntoView({ behavior: 'smooth' });
                }, 300);
            };
            reader.readAsDataURL(file);
        }

        // --- 2. RESIZE PROCESSING MESSAGE ---
        resizeBtn.addEventListener('click', function() {
            if (!cropperInstance) return;
            const targetKb = parseFloat(targetKbInput.value);
            if (!targetKb) return alert("Please enter Target KB!");

            // Button status update
            resizeBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Processing... Please wait`;
            resizeBtn.disabled = true;

            setTimeout(async () => {
                try {
                    let sourceCanvas = cropperInstance.getCroppedCanvas();
                    let w = parseInt(targetWidthInput.value) || sourceCanvas.width;
                    let h = parseInt(targetHeightInput.value) || sourceCanvas.height;

                    let scale = 1.0;
                    let bestBlob = null;

                    // Optimized Dual Engine (Size + Quality)
                    for (let attempt = 0; attempt < 5; attempt++) {
                        let tempW = Math.floor(w * scale);
                        let tempH = Math.floor(h * scale);

                        const canvas = document.createElement('canvas');
                        canvas.width = tempW;
                        canvas.height = tempH;
                        const ctx = canvas.getContext('2d');
                        ctx.fillStyle = "#FFFFFF";
                        ctx.fillRect(0, 0, tempW, tempH);
                        ctx.drawImage(sourceCanvas, 0, 0, tempW, tempH);

                        let low = 0.01, high = 1.0;
                        for (let j = 0; j < 25; j++) {
                            let q = (low + high) / 2;
                            const b = await new Promise(r => canvas.toBlob(r, 'image/jpeg', q));
                            if (b.size / 1024 <= targetKb) {
                                bestBlob = b;
                                low = q;
                            } else {
                                high = q;
                            }
                        }

                        if (low > 0.15 || scale < 0.5) break;
                        scale -= 0.15;
                    }

                    globalResizedBlob = bestBlob || await new Promise(r => sourceCanvas.toBlob(r, 'image/jpeg', 0.1));

                    finalPreview.src = URL.createObjectURL(globalResizedBlob);
                    finalImageSize.innerHTML = `Final Size: <b>${(globalResizedBlob.size / 1024).toFixed(2)} KB</b> <br> <small>Optimized for Mobile</small>`;
                    
                    resultArea.style.display = 'block';
                    resultArea.scrollIntoView({ behavior: 'smooth' });

                } catch (e) {
                    alert("Processing Error!");
                } finally {
                    // Reset Button
                    resizeBtn.innerHTML = `Crop, Resize & Save`;
                    resizeBtn.disabled = false;
                }
            }, 100);
        });

        downloadBtn.onclick = () => {
            if (!globalResizedBlob) return;
            const a = document.createElement('a');
            a.href = URL.createObjectURL(globalResizedBlob);
            a.download = `SHC_${targetKbInput.value}KB.jpg`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        };
    });
})();