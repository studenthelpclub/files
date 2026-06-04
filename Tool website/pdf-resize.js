// 1. GLOBAL INITIALIZATION (Desktop Fix)
const { jsPDF } = window.jspdf;
const pdfjsLib = window['pdfjs-dist/build/pdf'];
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';

const pdfInput = document.getElementById('pdfInput');
const pdfDropZone = document.getElementById('pdfDropZone');
const pdfSettings = document.getElementById('pdfSettings');
const selectedFileName = document.getElementById('selectedFileName');
const resizePdfBtn = document.getElementById('resizePdfBtn');
const pdfResultArea = document.getElementById('pdfResultArea');
const finalPdfSize = document.getElementById('finalPdfSize');
const downloadPdfBtn = document.getElementById('downloadPdfBtn');
const targetKbInput = document.getElementById('targetKb');
const previewContainer = document.getElementById('previewContainer');

let currentFile = null;
let resizedBlob = null; // To store the result for download
let resizedBlobUrl = null;

pdfDropZone.addEventListener('click', () => pdfInput.click());
pdfInput.addEventListener('change', (e) => { if (e.target.files[0]) handleFile(e.target.files[0]); });

function handleFile(file) {
    if (file.type !== "application/pdf") return alert("Please select a valid PDF file.");
    currentFile = file;
    selectedFileName.innerHTML = `<i class="fas fa-file-pdf"></i> Selected: ${file.name} (${(file.size/1024).toFixed(2)} KB)`;
    pdfSettings.style.display = 'block';
    pdfResultArea.style.display = 'none';
    pdfSettings.scrollIntoView({ behavior: 'smooth' });
}

resizePdfBtn.addEventListener('click', async () => {
    const targetKb = parseFloat(targetKbInput.value);
    if (!targetKb) return alert("Enter target KB.");

    resizePdfBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Engine Calibration...`;
    resizePdfBtn.disabled = true;

    try {
        const arrayBuffer = await currentFile.arrayBuffer();
        const pdfData = await pdfjsLib.getDocument({data: arrayBuffer}).promise;
        
        // --- STEP 1: High-Density DPI Scaling (Aapka Logic) ---
        let scale = targetKb > 1500 ? 5.5 : (targetKb > 800 ? 4.0 : 2.5);

        const getPages = async (s) => {
            let canvases = [];
            for (let i = 1; i <= pdfData.numPages; i++) {
                const page = await pdfData.getPage(i);
                const viewport = page.getViewport({scale: s});
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                canvas.height = viewport.height; 
                canvas.width = viewport.width;
                ctx.imageSmoothingEnabled = true;
                ctx.imageSmoothingQuality = 'high';
                await page.render({canvasContext: ctx, viewport: viewport}).promise;
                canvases.push(canvas);
            }
            return canvases;
        };

        let pagesCanvas = await getPages(scale);

        // --- STEP 2: Strict Binary Search (Aapka Logic) ---
        let minQ = 0.0001, maxQ = 1.0, bestBlob = null, bestSize = 0;

        for (let attempt = 0; attempt < 35; attempt++) {
            let q = (minQ + maxQ) / 2;
            const outPdf = new jsPDF({
                orientation: 'p',
                unit: 'pt',
                format: 'a4',
                compress: false
            });

            const pWidth = outPdf.internal.pageSize.getWidth();
            const pHeight = outPdf.internal.pageSize.getHeight();

            for (let j = 0; j < pagesCanvas.length; j++) {
                if (j > 0) outPdf.addPage();
                const imgData = pagesCanvas[j].toDataURL('image/jpeg', q);
                outPdf.addImage(imgData, 'JPEG', 0, 0, pWidth, pHeight, undefined, 'NONE');
            }
            
            let tempBlob = outPdf.output('blob');
            let currentSize = tempBlob.size / 1024;

            if (currentSize <= targetKb) {
                if (currentSize > bestSize) {
                    bestSize = currentSize;
                    bestBlob = tempBlob;
                }
                minQ = q;
            } else {
                maxQ = q;
            }

            if (attempt === 20 && bestSize < targetKb * 0.85 && scale < 8) {
                scale += 2.0;
                pagesCanvas = await getPages(scale);
                minQ = 0.5;
            }

            if (currentSize <= targetKb && (targetKb - currentSize) <= 10) break;
        }

        if (bestBlob) {
            resizedBlob = bestBlob; // Save blob for download
            if (resizedBlobUrl) URL.revokeObjectURL(resizedBlobUrl);
            resizedBlobUrl = URL.createObjectURL(bestBlob);

            // --- DUAL PREVIEW ENGINE (Phone + Desktop) ---
            const isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent);
            
            if (isMobile) {
                // Mobile Mode: Canvas Setup
                previewContainer.innerHTML = `
                    <p style="font-size:12px; color:#666; margin-bottom:5px;">Preview (Page 1)</p>
                    <canvas id="mobileCanvas" style="width:100%; border-radius:12px; border:1px solid #ddd; background:#fff;"></canvas>
                `;
                
                const canvas = document.getElementById('mobileCanvas');
                const context = canvas.getContext('2d');

                const reader = new FileReader();
                reader.onload = async function() {
                    try {
                        const typedarray = new Uint8Array(this.result);
                        // PDF load karein
                        const loadingTask = pdfjsLib.getDocument({data: typedarray});
                        const pdf = await loadingTask.promise;
                        
                        // Pehla page pakdein
                        const page = await pdf.getPage(1);
                        
                        // Mobile screen ke hisab se scale set karein
                        const windowWidth = window.innerWidth || document.documentElement.clientWidth;
                        const scale = (windowWidth * 0.8) / page.getViewport({scale: 1}).width;
                        const viewport = page.getViewport({scale: scale});

                        canvas.height = viewport.height;
                        canvas.width = viewport.width;

                        // Render start
                        await page.render({
                            canvasContext: context,
                            viewport: viewport
                        }).promise;
                        
                    } catch (e) {
                        console.error("Preview render failed:", e);
                        previewContainer.innerHTML = "<p style='color:red;'>Preview not available</p>";
                    }
                };
                reader.readAsArrayBuffer(bestBlob);
            } else {
                // Desktop Mode (Iframe)
                previewContainer.innerHTML = `<iframe src="${resizedBlobUrl}" style="width:100%; height:450px; border-radius:12px; border:1px solid #ddd;"></iframe>`;
            }

            finalPdfSize.innerText = `Final Size: ${(bestBlob.size / 1024).toFixed(2)} KB`;
            pdfResultArea.style.display = 'block';
            pdfResultArea.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert("Could not reach target. Try a higher KB.");
        }

    } catch (err) {
        alert("Precision Error.");
        console.error(err);
    } finally {
        resizePdfBtn.innerText = "Compress PDF";
        resizePdfBtn.disabled = false;
    }
});

// Download Functionality
downloadPdfBtn.onclick = () => {
    if (!resizedBlob) return;
    const link = document.createElement('a');
    link.href = URL.createObjectURL(resizedBlob);
    link.download = `Resized_SHC_${Date.now()}.pdf`;
    link.click();
};