const { jsPDF } = window.jspdf;

const imageInput = document.getElementById('imageInput');
const imageList = document.getElementById('imageList');
const pdfSettings = document.getElementById('pdfSettings');
const convertBtn = document.getElementById('convertBtn');
const resetBtn = document.getElementById('resetBtn');
const resultArea = document.getElementById('resultArea');
const downloadBtn = document.getElementById('downloadBtn');
const previewContainer = document.getElementById('previewContainer');
const orientationSelect = document.getElementById('orientation');

let selectedImages = [];
let finalPdfBlobUrl = null;

// File change listener
imageInput.addEventListener('change', (e) => {
    const files = e.target.files;
    if (files.length === 0) return;
    
    Array.from(files).forEach(file => {
        if (!file.type.startsWith('image/')) return;
        const reader = new FileReader();
        reader.onload = (event) => {
            selectedImages.push({ 
                name: file.name, 
                src: event.target.result,
                type: file.type 
            });
            updateUI();
        };
        reader.readAsDataURL(file);
    });
});

function updateUI() {
    imageList.innerHTML = selectedImages.length > 0 ? `<p style="font-weight:bold; margin-bottom:10px;">Images Added (${selectedImages.length}):</p>` : "";
    
    selectedImages.forEach((img, i) => {
        const item = document.createElement('div');
        item.style = "display:flex; justify-content:space-between; align-items:center; background:#fff; padding:12px; border-radius:10px; margin-bottom:10px; border:1px solid #eee;";
        item.innerHTML = `
            <div style="display:flex; align-items:center; gap:10px;">
                <img src="${img.src}" style="width:40px; height:40px; border-radius:5px; object-fit:cover;">
                <span style="font-size:12px; font-weight:500;">${img.name}</span>
            </div>
            <div style="display:flex; gap:15px;">
                <i class="fas fa-arrow-up" style="color:#198754; cursor:pointer;" onclick="moveImage(${i}, -1)"></i>
                <i class="fas fa-trash-alt" style="color:#dc3545; cursor:pointer;" onclick="removeImage(${i})"></i>
            </div>`;
        imageList.appendChild(item);
    });
    
    pdfSettings.style.display = selectedImages.length > 0 ? 'block' : 'none';
    resultArea.style.display = 'none';
}

window.moveImage = (idx, dir) => {
    const newIdx = idx + dir;
    if (newIdx >= 0 && newIdx < selectedImages.length) {
        [selectedImages[idx], selectedImages[newIdx]] = [selectedImages[newIdx], selectedImages[idx]];
        updateUI();
    }
};

window.removeImage = (i) => { 
    selectedImages.splice(i, 1); 
    updateUI(); 
};

resetBtn.onclick = () => { 
    selectedImages = []; 
    imageInput.value = "";
    updateUI(); 
    resultArea.style.display = 'none'; 
};

// --- PDF GENERATION LOGIC ---
convertBtn.addEventListener('click', async () => {
    if (selectedImages.length === 0) return;
    
    convertBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Converting...`;
    convertBtn.disabled = true;

    const pdf = new jsPDF({
        orientation: orientationSelect.value,
        unit: 'pt',
        format: 'a4'
    });

    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = pdf.internal.pageSize.getHeight();

    for (let i = 0; i < selectedImages.length; i++) {
        const img = selectedImages[i];
        if (i > 0) pdf.addPage();
        const format = img.type.includes('png') ? 'PNG' : 'JPEG';
        pdf.addImage(img.src, format, 0, 0, pdfWidth, pdfHeight, undefined, 'NONE');
    }

    const blob = pdf.output('blob');
    if (finalPdfBlobUrl) URL.revokeObjectURL(finalPdfBlobUrl);
    finalPdfBlobUrl = URL.createObjectURL(blob);
    
    // --- DEVICE DETECTION LOGIC ---
    const isMobile = window.innerWidth <= 768;

    if (isMobile) {
        // Phone par Preview Container khali rakhein
        previewContainer.innerHTML = "";
    } else {
        // PC par Iframe Preview dikhayein
        previewContainer.innerHTML = `<iframe src="${finalPdfBlobUrl}"></iframe>`;
    }

    resultArea.style.display = 'block';
    convertBtn.innerHTML = "Create PDF Now";
    convertBtn.disabled = false;
    resultArea.scrollIntoView({ behavior: 'smooth' });
});

downloadBtn.onclick = () => {
    if (!finalPdfBlobUrl) return;
    const a = document.createElement('a');
    a.href = finalPdfBlobUrl;
    a.download = `SHC_Image_to_PDF.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
};