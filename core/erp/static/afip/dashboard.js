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

    // Botones para generar certificado y autorizar WS desde el dashboard
    document.querySelectorAll('.btn-generate-cert').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const configId = this.getAttribute('data-config-id');
            const environment = this.getAttribute('data-environment');

            const certConfigId = document.getElementById('cert_config_id');
            const certType = document.getElementById('cert_type');
            const certUsername = document.getElementById('cert_username');
            const certPassword = document.getElementById('cert_password');
            const certErrorBlock = document.getElementById('cert-error-block');

            if (certConfigId) certConfigId.value = configId;
            if (certType) certType.value = environment === 'prod' ? 'prod' : 'dev';

            // Limpiar campos de credenciales
            if (certUsername) certUsername.value = '';
            if (certPassword) certPassword.value = '';
            if (certErrorBlock) certErrorBlock.style.display = 'none';

            showGenerateCertModal();
        });
    });

    document.querySelectorAll('.btn-auth-ws').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const configId = this.getAttribute('data-config-id');

            const authConfigId = document.getElementById('auth_config_id');
            const authUsername = document.getElementById('auth_username');
            const authPassword = document.getElementById('auth_password');
            const authErrorBlock = document.getElementById('auth-error-block');

            if (authConfigId) authConfigId.value = configId;

            // Limpiar campos de credenciales
            if (authUsername) authUsername.value = '';
            if (authPassword) authPassword.value = '';
            if (authErrorBlock) authErrorBlock.style.display = 'none';

            showAuthWebServiceModal();
        });
    });

    // Manejar el formulario de generación de certificados
    const generateCertForm = document.getElementById('generateCertForm');
    if (generateCertForm) {
        generateCertForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const errorBlock = document.getElementById('cert-error-block');

            // Verificar que se haya seleccionado una configuración
            const configId = document.getElementById('cert_config_id').value;
            if (!configId) {
                errorBlock.textContent = 'Debe seleccionar una configuración AFIP';
                errorBlock.style.display = 'block';
                return;
            }

            // Agregar acción de generar certificado
            formData.append('action', 'generate_certificate');

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
                    const modal = bootstrap.Modal.getInstance(document.getElementById('generateCertModal'));
                    modal.hide();
                    alert(data.message || 'Certificado generado exitosamente');
                    location.reload();
                } else {
                    errorBlock.textContent = data.error || 'Error al generar certificado';
                    errorBlock.style.display = 'block';
                }
            })
            .catch(error => {
                errorBlock.textContent = 'Error de conexión: ' + error;
                errorBlock.style.display = 'block';
            });
        });
    }

    // Botón de generar certificado dentro del modal
    const btnGenerateCert = document.getElementById('btnGenerateCert');
    if (btnGenerateCert) {
        btnGenerateCert.addEventListener('click', function() {
            generateCertForm.dispatchEvent(new Event('submit'));
        });
    }

    // Manejar el formulario de autorización de Web Service
    const authWebServiceForm = document.getElementById('authWebServiceForm');
    if (authWebServiceForm) {
        authWebServiceForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const errorBlock = document.getElementById('auth-error-block');

            // Verificar que se haya seleccionado una configuración
            const configId = document.getElementById('auth_config_id').value;
            if (!configId) {
                errorBlock.textContent = 'Debe seleccionar una configuración AFIP';
                errorBlock.style.display = 'block';
                return;
            }

            // Agregar acción de autorizar web service
            formData.append('action', 'auth_web_service');

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
                    const modal = bootstrap.Modal.getInstance(document.getElementById('authWebServiceModal'));
                    modal.hide();
                    alert(data.message || 'Web Service autorizado exitosamente');
                    location.reload();
                } else {
                    errorBlock.textContent = data.error || 'Error al autorizar Web Service';
                    errorBlock.style.display = 'block';
                }
            })
            .catch(error => {
                errorBlock.textContent = 'Error de conexión: ' + error;
                errorBlock.style.display = 'block';
            });
        });
    }

    // Botón de autorizar WS dentro del modal
    const btnAuthWS = document.getElementById('btnAuthWS');
    if (btnAuthWS) {
        btnAuthWS.addEventListener('click', function() {
            authWebServiceForm.dispatchEvent(new Event('submit'));
        });
    }
});
