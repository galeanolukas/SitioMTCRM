// Form AFIP JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const companySelect = document.getElementById('id_company');
    const cuitInput = document.getElementById('id_cuit');
    
    if (companySelect && cuitInput) {
        companySelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            const cuitMatch = selectedOption.text.match(/CUIT:\s*([^\)]+)/);
            if (cuitMatch) {
                cuitInput.value = cuitMatch[1].trim();
            }
        });
    }
});
