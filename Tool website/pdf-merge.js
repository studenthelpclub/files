// 1. Library Initialization
const { jsPDF } = window.jspdf;
const { PDFDocument } = PDFLib;
const pdfjsLib = window['pdfjs-dist/build/pdf'];
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';

// 2. Elements Mapping
const pdfInput = document.getElementById('pdfInput');
const pdfDropZone = document.getElementById('pdfDropZone');
const fileList = document.getElementById('fileList');
const mergeBtn = document.getElementById('mergeBtn');
const fastMergeBtn = document.getElementById('fastMergeBtn');
const actionButtons = document.getElementById('actionButtons');
const pdfResultArea = document.getElementById('pdfResultArea');
const downloadPdfBtn = document.getElementById('downloadPdfBtn');
const targetKbInput = document.getElementById('targetKb');
const finalPdfSize = document.getElementById('finalPdfSize');
const previewContainer = document.getElementById('previewContainer');

let selectedFiles = [];
let globalMergedBlob = null; 

// 3. File Handling Logic
pdfDropZone.addEventListener('click', () => pdfInput.click());
pdfInput.addEventListener('change', (e) => handleFiles(e.target.files));

function handleFiles(files) {
    const newFiles = Array.from(files).filter(f => f.type === "application/pdf");
    selectedFiles = [...selectedFiles, ...newFiles];
    updateUI();
}

function updateUI() {
    fileList.innerHTML = selectedFiles.length > 0 ? `<p style="font-weight:bold; margin-bottom:10px;">Selected Files (${selectedFiles.length}):</p>` : "";
    selectedFiles.forEach((f, i) => {
        const item = document.createElement('div');
        item.className = "file-item";
        item.innerHTML = `<span><i class="fas fa-file-pdf" style="color:#e74c3c"></i> ${f.name}</span>
            <div>
                <i class="fas fa-arrow-up" style="cursor:pointer; color:#0d6efd; margin-right:12px;" onclick="moveFile(${i}, -1)"></i>
                <i class="fas fa-trash-alt" style="color:red; cursor:pointer;" onclick="removeFile(${i})"></i>
            </div>`;
        fileList.appendChild(item);
    });
    const hasFiles = selectedFiles.length > 0;
    actionButtons.style.display = hasFiles ? 'flex' : 'none';
    const resizeBox = document.getElementById('resizeOptionBox');
    if(resizeBox) resizeBox.style.display = hasFiles ? 'block' : 'none';
}

window.moveFile = (idx, dir) => {
    const newIdx = idx + dir;
    if (newIdx >= 0 && newIdx < selectedFiles.length) {
        [selectedFiles[idx], selectedFiles[newIdx]] = [selectedFiles[newIdx], selectedFiles[idx]];
        updateUI();
    }
};

window.removeFile = (i) => { selectedFiles.splice(i, 1); updateUI(); };
document.getElementById('resetPdfBtn').onclick = () => location.reload();

// 4. Fast Merge (Original Quality)
fastMergeBtn.addEventListener('click', async () => {
    fastMergeBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Merging...`;
    try {
        const mergedPdf = await PDFDocument.create();
        for (const f of selectedFiles) {
            const pdf = await PDFDocument.load(await f.arrayBuffer());
            const pages = await mergedPdf.copyPages(pdf, pdf.getPageIndices());
            pages.forEach(p => mergedPdf.addPage(p));
        }
        const blob = new Blob([await mergedPdf.save()], { type: 'application/pdf' });
        showResult(blob);
    } catch(e) { alert("Error merging PDFs"); }
    fastMergeBtn.innerHTML = `<i class="fas fa-bolt"></i> Fast Merge`;
});

// 5. Merge & Resize Logic (Precision Engine)
mergeBtn.addEventListener('click', async () => {
    const targetKb = parseFloat(targetKbInput.value);
    if (!targetKb) return alert("Please enter Target KB");

    mergeBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Processing...`;
    mergeBtn.disabled = true;
    
    try {
        let scale = targetKb > 1500 ? 5.5 : (targetKb > 800 ? 4.0 : 2.5);

        const getCanvases = async (s) => {
            let canvases = [];
            for (const f of selectedFiles) {
                const pdf = await pdfjsLib.getDocument({data: await f.arrayBuffer()}).promise;
                for (let i = 1; i <= pdf.numPages; i++) {
                    const page = await pdf.getPage(i);
                    const viewport = page.getViewport({scale: s});
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    canvas.height = viewport.height; 
                    canvas.width = viewport.width;
                    await page.render({canvasContext: ctx, viewport: viewport}).promise;
                    canvases.push(canvas);
                }
            }
            return canvases;
        };

        let pagesCanvas = await getCanvases(scale);
        let minQ = 0.0001, maxQ = 1.0, bestBlob = null, bestSize = 0;

        for (let i = 0; i < 35; i++) {
            let q = (minQ + maxQ) / 2;
            const outPdf = new jsPDF({ orientation: 'p', unit: 'pt', format: 'a4', compress: false });
            const pWidth = outPdf.internal.pageSize.getWidth();
            const pHeight = outPdf.internal.pageSize.getHeight();

            pagesCanvas.forEach((c, idx) => {
                if (idx > 0) outPdf.addPage();
                const imgData = c.toDataURL('image/jpeg', q);
                outPdf.addImage(imgData, 'JPEG', 0, 0, pWidth, pHeight, undefined, 'NONE');
            });
            
            const tempBlob = outPdf.output('blob');
            const currentSizeKb = tempBlob.size / 1024;

            if (currentSizeKb <= targetKb) {
                if (currentSizeKb > bestSize) {
                    bestSize = currentSizeKb;
                    bestBlob = tempBlob;
                }
                minQ = q;
            } else {
                maxQ = q;
            }
            if (i === 20 && bestSize < targetKb * 0.85 && scale < 8) {
                scale += 2.0;
                pagesCanvas = await getCanvases(scale);
                minQ = 0.5;
            }
            if (currentSizeKb <= targetKb && (targetKb - currentSizeKb) <= 10) break;
        }

        if (bestBlob) showResult(bestBlob);
        else alert("Could not reach target accurately.");

    } catch(e) { alert("Precision error."); }
    finally {
        mergeBtn.innerHTML = `<i class="fas fa-compress-arrows-alt"></i> Merge & Resize`;
        mergeBtn.disabled = false;
    }
});

// 6. Final Multi-Page Preview Engine (Fixed for Mobile)
async function showResult(blob) {
    globalMergedBlob = blob;
    previewContainer.innerHTML = ''; 
    
    try {
        const reader = new FileReader();
        reader.onload = async function() {
            const typedarray = new Uint8Array(this.result);
            const pdf = await pdfjsLib.getDocument({data: typedarray}).promise;
            
            // Loop for ALL pages
            for (let i = 1; i <= pdf.numPages; i++) {
                const page = await pdf.getPage(i);
                
                const canvas = document.createElement('canvas');
                canvas.style.width = "100%";
                canvas.style.borderRadius = "10px";
                canvas.style.border = "1px solid #ddd";
                canvas.style.marginBottom = "15px";
                canvas.style.background = "#fff";
                previewContainer.appendChild(canvas);

                const context = canvas.getContext('2d');
                const baseViewport = page.getViewport({scale: 1.0});
                
                // Calculate display scale
                const containerWidth = previewContainer.clientWidth || 300;
                const displayScale = (containerWidth / baseViewport.width) * 1.5;
                const viewport = page.getViewport({scale: displayScale});

                canvas.height = viewport.height;
                canvas.width = viewport.width;

                await page.render({canvasContext: context, viewport: viewport}).promise;
            }
        };
        reader.readAsArrayBuffer(blob);
    } catch (e) {
        console.error("Preview failed:", e);
        previewContainer.innerHTML = "<p>Preview error, file is ready to download.</p>";
    }

    finalPdfSize.innerText = `Final Size: ${(blob.size / 1024).toFixed(2)} KB`;
    pdfResultArea.style.display = 'block';
    pdfResultArea.scrollIntoView({ behavior: 'smooth' });
}

// 7. Secure Download Logic (Mobile-Proof)
downloadPdfBtn.onclick = (e) => {
    e.preventDefault();
    if (!globalMergedBlob) return alert("File not ready!");
    
    const name = document.getElementById('customFileName').value.trim() || "Merged_Document_SHC";
    const url = window.URL.createObjectURL(globalMergedBlob);
    
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `${name}.pdf`;
    
    document.body.appendChild(a);
    a.click();
    
    setTimeout(() => {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }, 2000);
};