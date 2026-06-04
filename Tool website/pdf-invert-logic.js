const pdfInput = document.getElementById('pdfInput');
const dropZone = document.getElementById('dropZone');
const invertBtn = document.getElementById('invertBtn');
const downloadBtn = document.getElementById('downloadBtn');
const successMsg = document.getElementById('successMsg');
const fileNameDisplay = document.getElementById('selectedFileName');
const statusText = document.getElementById('statusText');

let invertedBlobUrl = null;
let currentFileName = "";

// Selection Logic
dropZone.onclick = () => pdfInput.click();
pdfInput.onchange = (e) => handleFile(e.target.files[0]);

function handleFile(file) {
    if (file && file.type === "application/pdf") {
        currentFileName = file.name;
        fileNameDisplay.innerText = "Selected: " + currentFileName;
        statusText.innerText = "File Ready";
        invertBtn.style.display = "block";
        
        // Reset UI if a new file is selected
        downloadBtn.style.display = "none";
        successMsg.style.display = "none";
    }
}

// Invert Logic (Same Logic, No Preview)
invertBtn.onclick = async () => {
    const file = pdfInput.files[0];
    if (!file) return;

    invertBtn.innerText = "Processing... Please wait";
    invertBtn.disabled = true;

    try {
        const arrayBuffer = await file.arrayBuffer();
        const pdfDoc = await PDFLib.PDFDocument.load(arrayBuffer);
        const pages = pdfDoc.getPages();

        pages.forEach(page => {
            const { width, height } = page.getSize();
            page.drawRectangle({
                x: 0, y: 0, width, height,
                color: PDFLib.rgb(1, 1, 1),
                blendMode: PDFLib.BlendMode.Difference,
            });
        });

        const invertedBytes = await pdfDoc.save();
        
        // Create Blob and Download URL
        if (invertedBlobUrl) URL.revokeObjectURL(invertedBlobUrl);
        invertedBlobUrl = URL.createObjectURL(new Blob([invertedBytes], { type: 'application/pdf' }));

        // UI Updates: Hide Invert Button, Show Download Button
        invertBtn.style.display = "none";
        successMsg.style.display = "block";
        downloadBtn.style.display = "block";

    } catch (err) {
        alert("Error processing PDF!");
        console.error(err);
        invertBtn.innerText = "Invert Colors Now";
        invertBtn.disabled = false;
    }
};

// Download Logic
downloadBtn.onclick = () => {
    const link = document.createElement('a');
    link.href = invertedBlobUrl;
    link.download = "Inverted_SHC_" + currentFileName;
    link.click();
};