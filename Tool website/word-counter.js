// Variable Selection
const textInput = document.getElementById('textInput');
const wordCount = document.getElementById('wordCount');
const charCount = document.getElementById('charCount');
const copyBtn = document.getElementById('copyBtn');

// 1. Real-time Counter Logic
textInput.addEventListener('input', () => {
    const text = textInput.value.trim();
    
    // Character Count (including spaces)
    charCount.innerText = textInput.value.length;
    
    // Word Count Logic
    if (text === "") {
        wordCount.innerText = "0";
    } else {
        // Regex use kiya hai taaki extra spaces count na hon
        const words = text.split(/\s+/);
        wordCount.innerText = words.length;
    }
});

// 2. Case Conversion Functions
function changeCase(type) {
    let text = textInput.value;
    if (!text) return; // Agar empty hai toh kuch na karein

    switch(type) {
        case 'upper':
            textInput.value = text.toUpperCase();
            break;
        case 'lower':
            textInput.value = text.toLowerCase();
            break;
        case 'sentence':
            // Har sentence ka pehla letter capital karega
            textInput.value = text.toLowerCase().replace(/(^\s*\w|[\.\!\?]\s*\w)/g, c => c.toUpperCase());
            break;
    }
}

// 3. Clear Text Logic
function clearText() {
    if (confirm("Are you sure you want to clear the text?")) {
        textInput.value = "";
        wordCount.innerText = "0";
        charCount.innerText = "0";
    }
}

// 4. Copy to Clipboard Logic
function copyText() {
    if (!textInput.value) {
        alert("Please enter some text first!");
        return;
    }

    textInput.select();
    textInput.setSelectionRange(0, 99999); // Mobile compatibility ke liye

    try {
        navigator.clipboard.writeText(textInput.value);
        
        // Success Feedback
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        copyBtn.style.background = "#157347"; // Darker Green
        
        setTimeout(() => {
            copyBtn.innerHTML = originalText;
            copyBtn.style.background = "#198754"; // Original Green
        }, 2000);
    } catch (err) {
        alert("Unable to copy. Please copy manually.");
    }
}