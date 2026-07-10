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
    // Inicializar el campo CUIT con la empresa seleccionada por defecto
    updateCuitDisplay();
    const modal = new bootstrap.Modal(document.getElementById('createConfigModal'));
    modal.show();
}

function updateCuitDisplay() {
    const companySelect = document.getElementById('company_id_select');
    const selectedCompanyId = companySelect.value;
    
    // Obtener CUITs del atributo data-cuits
    const cuitsData = companySelect.getAttribute('data-cuits');
    const cuitsMap = {};
    
    if (cuitsData) {
        cuitsData.split(',').forEach(item => {
            const [id, cuit] = item.split(':');
            cuitsMap[id] = cuit;
        });
    }
    
    // Actualizar el campo CUIT con el valor de la empresa seleccionada
    const cuitValue = cuitsMap[selectedCompanyId] || '';
    document.getElementById('cuit_display').value = cuitValue;
    
    // Actualizar el campo oculto company_id
    document.getElementById('company_id').value = selectedCompanyId;
}

function showGenerateCertModal() {
    try {
        const modalElement = document.getElementById('generateCertModal');
        if (!modalElement) {
            console.error('Modal element not found');
            alert('Error: No se encontró el modal de generación de certificados');
            return;
        }

        if (typeof bootstrap === 'undefined') {
            console.error('Bootstrap is not loaded');
            alert('Error: Bootstrap no está cargado');
            return;
        }

        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    } catch (error) {
        console.error('Error al abrir modal:', error);
        alert('Error al abrir el modal: ' + error.message);
    }
}

function showAuthWebServiceModal() {
    try {
        const modalElement = document.getElementById('authWebServiceModal');
        if (!modalElement) {
            console.error('Modal element not found');
            alert('Error: No se encontró el modal de autorización de Web Service');
            return;
        }

        if (typeof bootstrap === 'undefined') {
            console.error('Bootstrap is not loaded');
            alert('Error: Bootstrap no está cargado');
            return;
        }

        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    } catch (error) {
        console.error('Error al abrir modal:', error);
        alert('Error al abrir el modal: ' + error.message);
    }
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

            // Asegurar que el campo company_id esté actualizado antes de enviar
            updateCuitDisplay();

            const formData = new FormData(this);
            const errorBlock = document.getElementById('error-block');

            // Verificar que company_id no esté vacío
            const companyId = document.getElementById('company_id').value;
            if (!companyId) {
                errorBlock.textContent = 'Debe seleccionar una empresa';
                errorBlock.classList.remove('d-none');
                return;
            }

            // Agregar acción de crear configuración
            formData.append('action', 'create_config');

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
