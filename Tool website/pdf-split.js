const { PDFDocument } = PDFLib;

const pdfInput = document.getElementById('pdfInput');
const pdfDropZone = document.getElementById('pdfDropZone');
const splitSettings = document.getElementById('splitSettings');
const pdfInfo = document.getElementById('pdfInfo');
const pageRangeInput = document.getElementById('pageRange');
const splitPdfBtn = document.getElementById('splitPdfBtn');
const pdfResultArea = document.getElementById('pdfResultArea');
const downloadPdfBtn = document.getElementById('downloadPdfBtn');
const previewContainer = document.getElementById('previewContainer');
const resultInfo = document.getElementById('resultInfo');

let currentPdfBytes = null;
let totalPagesCount = 0;
let splitBlobUrl = null;

// File Selection
pdfDropZone.addEventListener('click', () => pdfInput.click());
pdfInput.addEventListener('change', (e) => { if (e.target.files[0]) loadPdf(e.target.files[0]); });

async function loadPdf(file) {
    if (file.type !== "application/pdf") return alert("Please select a valid PDF file.");
    
    currentPdfBytes = await file.arrayBuffer();
    const pdfDoc = await PDFDocument.load(currentPdfBytes);
    totalPagesCount = pdfDoc.getPageCount();
    
    pdfInfo.innerHTML = `<i class="fas fa-file-alt"></i> File: ${file.name} <br> <i class="fas fa-copy"></i> Total Pages: ${totalPagesCount}`;
    splitSettings.style.display = 'block';
    pdfResultArea.style.display = 'none';
    splitSettings.scrollIntoView({ behavior: 'smooth' });
}

// Split Engine
splitPdfBtn.addEventListener('click', async () => {
    const rangeStr = pageRangeInput.value.trim();
    if (!rangeStr) return alert("Please enter page numbers to extract.");

    splitPdfBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Processing...`;
    splitPdfBtn.disabled = true;
    
    try {
        const pagesToExtract = [];
        const parts = rangeStr.split(',');

        parts.forEach(part => {
            if (part.includes('-')) {
                const [start, end] = part.split('-').map(Number);
                for (let i = start; i <= end; i++) {
                    if (i > 0 && i <= totalPagesCount) pagesToExtract.push(i - 1);
                }
            } else {
                const p = Number(part.trim());
                if (p > 0 && p <= totalPagesCount) pagesToExtract.push(p - 1);
            }
        });

        // Remove duplicates and sort pages
        const uniquePages = [...new Set(pagesToExtract)].sort((a, b) => a - b);

        if (uniquePages.length === 0) throw new Error("Invalid page numbers.");

        const sourcePdf = await PDFDocument.load(currentPdfBytes);
        const newPdf = await PDFDocument.create();
        
        const copiedPages = await newPdf.copyPages(sourcePdf, uniquePages);
        copiedPages.forEach(p => newPdf.addPage(p));

        const pdfBytes = await newPdf.save();
        
        if (splitBlobUrl) URL.revokeObjectURL(splitBlobUrl);
        splitBlobUrl = URL.createObjectURL(new Blob([pdfBytes], { type: 'application/pdf' }));

        previewContainer.innerHTML = `<iframe src="${splitBlobUrl}" style="width:100%; height:400px; border-radius:12px; border:1px solid #ddd;"></iframe>`;
        resultInfo.innerText = `Extracted ${uniquePages.length} pages. Ready to download!`;
        pdfResultArea.style.display = 'block';
        pdfResultArea.scrollIntoView({ behavior: 'smooth' });

    } catch (e) { 
        alert("Error: " + e.message); 
    } finally { 
        splitPdfBtn.innerText = "Extract & Download PDF"; 
        splitPdfBtn.disabled = false;
    }
});

downloadPdfBtn.onclick = () => {
    const a = document.createElement('a');
    a.href = splitBlobUrl;
    a.download = `Split_Result_SHC.pdf`;
    a.click();
};