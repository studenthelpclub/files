pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';

const pdfInput = document.getElementById('pdfInput');
const dropZone = document.getElementById('dropZone');
const convertSettings = document.getElementById('convertSettings');
const pdfNameDisplay = document.getElementById('pdfNameDisplay');
const convertBtn = document.getElementById('convertBtn');
const resultArea = document.getElementById('resultArea');
const imageGallery = document.getElementById('imageGallery');

let currentPdfDoc = null;

// File Upload Logic
dropZone.addEventListener('click', () => pdfInput.click());
pdfInput.addEventListener('change', (e) => { if (e.target.files[0]) handlePdf(e.target.files[0]); });

async function handlePdf(file) {
    if (file.type !== "application/pdf") return alert("Please upload a valid PDF file.");
    
    try {
        const arrayBuffer = await file.arrayBuffer();
        currentPdfDoc = await pdfjsLib.getDocument({data: arrayBuffer}).promise;
        
        pdfNameDisplay.innerHTML = `<i class="fas fa-file-pdf"></i> Selected: ${file.name} <br> <i class="fas fa-layer-group"></i> Total Pages: ${currentPdfDoc.numPages}`;
        convertSettings.style.display = 'block';
        resultArea.style.display = 'none';
        convertSettings.scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
        alert("Error loading PDF.");
    }
}

// Conversion Logic
convertBtn.addEventListener('click', async () => {
    if (!currentPdfDoc) return;
    
    convertBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Converting Pages...`;
    convertBtn.disabled = true;
    imageGallery.innerHTML = ""; 

    try {
        for (let i = 1; i <= currentPdfDoc.numPages; i++) {
            const page = await currentPdfDoc.getPage(i);
            const viewport = page.getViewport({scale: 2.0}); // High definition scale
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;

            await page.render({canvasContext: context, viewport: viewport}).promise;
            const imageUrl = canvas.toDataURL('image/jpeg', 0.9);
            
            const wrapper = document.createElement('div');
            wrapper.style.cssText = "background:#fff; padding:12px; border-radius:15px; border:1px solid #eee; text-align:center; box-shadow: 0 4px 10px rgba(0,0,0,0.05); animation: popIn 0.3s ease-out;";
            wrapper.innerHTML = `
                <img src="${imageUrl}" style="width:100%; border-radius:8px; margin-bottom:10px; border:1px solid #f0f0f0;">
                <p style="font-size:12px; font-weight:bold; margin-bottom:10px; color:#555;">Page ${i}</p>
                <a href="${imageUrl}" download="SHC_Page_${i}.jpg" class="download-btn" style="padding: 10px; font-size: 12px; text-decoration: none; display: block; background:#198754;">
                    <i class="fas fa-download"></i> Download JPG
                </a>
            `;
            imageGallery.appendChild(wrapper);
        }
        resultArea.style.display = 'block';
        resultArea.scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
        alert("Error during conversion.");
    } finally {
        convertBtn.innerHTML = "Convert All Pages to JPG";
        convertBtn.disabled = false;
    }
});