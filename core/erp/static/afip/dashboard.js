// Dashboard AFIP JavaScript

function createAfipConfig(companyId) {
    if (companyId) {
        document.getElementById('company_id').value = companyId;
        const companySelect = document.getElementById('company_id_select');
        companySelect.value = companyId;
        updateCuitDisplay();
    }
    const modal = new bootstrap.Modal(document.getElementById('createConfigModal'));
    modal.show();
}

function showCompanySelector() {
    const modal = new bootstrap.Modal(document.getElementById('createConfigModal'));
    modal.show();
}

function updateCuitDisplay() {
    const companySelect = document.getElementById('company_id_select');
    const selectedOption = companySelect.options[companySelect.selectedIndex];
    const cuitText = selectedOption.text;
    
    // Extraer CUIT del texto de la opción
    const cuitMatch = cuitText.match(/CUIT:\s*([^\)]+)/);
    if (cuitMatch) {
        document.getElementById('cuit_display').value = cuitMatch[1].trim();
    } else {
        document.getElementById('cuit_display').value = '';
    }
    
    // Actualizar el campo oculto company_id
    document.getElementById('company_id').value = companySelect.value;
}

document.addEventListener('DOMContentLoaded', function() {
    const companySelect = document.getElementById('company_id_select');
    if (companySelect) {
        companySelect.addEventListener('change', updateCuitDisplay);
    }
    
    const createConfigForm = document.getElementById('createConfigForm');
    if (createConfigForm) {
        createConfigForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const errorBlock = document.getElementById('error-block');
            
            fetch('', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('createConfigModal'));
                    modal.hide();
                    location.reload();
                } else {
                    errorBlock.textContent = data.error || 'Error al crear configuración';
                    errorBlock.classList.remove('d-none');
                }
            })
            .catch(error => {
                errorBlock.textContent = 'Error de conexión: ' + error;
                errorBlock.classList.remove('d-none');
            });
        });
    }
});
