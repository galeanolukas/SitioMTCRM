// Test AFIP JavaScript

function testConnection(companyId) {
    if (companyId) {
        document.getElementById('company_id').value = companyId;
        const companySelect = document.getElementById('company_id_select');
        companySelect.value = companyId;
    }
    const modal = new bootstrap.Modal(document.getElementById('testModal'));
    modal.show();
}

document.addEventListener('DOMContentLoaded', function() {
    const testTypeSelect = document.getElementById('test_type');
    const cuitGroup = document.getElementById('cuit_group');
    
    if (testTypeSelect) {
        testTypeSelect.addEventListener('change', function() {
            if (this.value === 'get_taxpayer') {
                cuitGroup.classList.remove('d-none');
            } else {
                cuitGroup.classList.add('d-none');
            }
        });
    }
    
    const companySelect = document.getElementById('company_id_select');
    if (companySelect) {
        companySelect.addEventListener('change', function() {
            document.getElementById('company_id').value = this.value;
        });
    }
    
    const testForm = document.getElementById('testForm');
    if (testForm) {
        testForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const testType = formData.get('test_type');
            const errorBlock = document.getElementById('error-block');
            const successBlock = document.getElementById('success-block');
            
            // Set action based on test type
            formData.set('action', testType);
            
            errorBlock.classList.add('d-none');
            successBlock.classList.add('d-none');
            
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
                    if (testType === 'test_connection') {
                        successBlock.textContent = 'Conexión exitosa: ' + JSON.stringify(data.status);
                    } else if (testType === 'get_taxpayer') {
                        successBlock.textContent = 'Contribuyente: ' + JSON.stringify(data.taxpayer);
                    }
                    successBlock.classList.remove('d-none');
                } else {
                    errorBlock.textContent = data.error || 'Error en la prueba';
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
