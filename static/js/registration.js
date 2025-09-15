// Updated by Claude AI at 2025-01-15 14:35:12
// Form interactions for Vancouver CBC Registration
document.addEventListener('DOMContentLoaded', function() {
    initializeFormHandlers();
    initializeValidation();
    initializeParticipationTypeValidation();
});

function initializeFormHandlers() {
    const areaDropdown = document.getElementById('preferred_area');
    const form = document.querySelector('form');

    // Handle dropdown changes
    if (areaDropdown) {
        areaDropdown.addEventListener('change', function(e) {
            // Skip processing if this is a programmatic update from the map
            if (window.isUpdatingProgrammatically) {
                return;
            }

            const selectedValue = e.target.value;

            if (selectedValue && typeof window.highlightAreaFromDropdown === 'function') {
                // Update map selection if map is loaded
                window.highlightAreaFromDropdown(selectedValue);
            }

            // Clear any validation errors
            clearFieldError('preferred_area');
        });
    }

    // Handle form submission
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!validateForm()) {
                e.preventDefault();
                return false;
            }

            // Show loading state
            showFormLoading(true);
        });
    }

    // Add input validation on blur
    const requiredFields = ['first_name', 'last_name', 'email', 'skill_level', 'experience', 'preferred_area'];
    requiredFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('blur', function() {
                validateField(fieldId);
            });

            field.addEventListener('input', function() {
                clearFieldError(fieldId);
            });
        }
    });

    // Email validation on input
    const emailField = document.getElementById('email');
    if (emailField) {
        emailField.addEventListener('input', function() {
            if (this.value && !isValidEmail(this.value)) {
                showFieldError('email', 'Please enter a valid email address');
            } else {
                clearFieldError('email');
            }
        });
    }
}

function initializeValidation() {
    // Add visual feedback for required fields
    const requiredFields = document.querySelectorAll('input[required], select[required]');
    requiredFields.forEach(field => {
        const label = document.querySelector(`label[for="${field.id}"]`);
        if (label && !label.textContent.includes('*')) {
            label.innerHTML = label.innerHTML + ' <span class="text-danger">*</span>';
        }
    });
}

function validateForm() {
    let isValid = true;
    const errors = [];

    // Validate required fields
    const requiredFields = [
        { id: 'first_name', name: 'First name' },
        { id: 'last_name', name: 'Last name' },
        { id: 'email', name: 'Email address' },
        { id: 'skill_level', name: 'Birding skill level' },
        { id: 'experience', name: 'CBC experience' },
        { id: 'preferred_area', name: 'Preferred area' }
    ];

    requiredFields.forEach(field => {
        const element = document.getElementById(field.id);
        if (!element || !element.value.trim()) {
            showFieldError(field.id, `${field.name} is required`);
            errors.push(`${field.name} is required`);
            isValid = false;
        }
    });

    // Validate participation type is selected
    const participationTypeRadios = document.querySelectorAll('input[name="participation_type"]');
    const participationTypeSelected = Array.from(participationTypeRadios).some(radio => radio.checked);
    if (!participationTypeSelected) {
        errors.push('Please select how you would like to participate');
        isValid = false;
    }

    // Validate FEEDER participant constraints
    const feederRadio = document.getElementById('feeder');
    if (feederRadio && feederRadio.checked) {
        const areaDropdown = document.getElementById('preferred_area');
        const leadershipCheckbox = document.getElementById('interested_in_leadership');
        
        if (areaDropdown && areaDropdown.value === 'UNASSIGNED') {
            showFieldError('preferred_area', 'Feeder counters must select a specific area');
            errors.push('Feeder counters must select a specific area');
            isValid = false;
        }
        
        if (leadershipCheckbox && leadershipCheckbox.checked) {
            showFieldError('interested_in_leadership', 'Feeder counters cannot be area leaders');
            errors.push('Feeder counters cannot be area leaders');
            isValid = false;
        }
    }

    // Validate email format
    const emailField = document.getElementById('email');
    if (emailField && emailField.value && !isValidEmail(emailField.value)) {
        showFieldError('email', 'Please enter a valid email address');
        errors.push('Please enter a valid email address');
        isValid = false;
    }

    // Show summary of errors if any
    if (errors.length > 0) {
        showFormErrors(errors);
    }

    return isValid;
}

function validateField(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return true;

    if (field.hasAttribute('required') && !field.value.trim()) {
        const label = document.querySelector(`label[for="${fieldId}"]`);
        const fieldName = label ? label.textContent.replace('*', '').trim() : fieldId;
        showFieldError(fieldId, `${fieldName} is required`);
        return false;
    }

    if (fieldId === 'email' && field.value && !isValidEmail(field.value)) {
        showFieldError(fieldId, 'Please enter a valid email address');
        return false;
    }

    clearFieldError(fieldId);
    return true;
}

function isValidEmail(email) {
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return emailRegex.test(email);
}

function showFieldError(fieldId, message) {
    const field = document.getElementById(fieldId);
    if (!field) return;

    // Add error class
    field.classList.add('is-invalid');

    // Remove existing error message
    const existingError = field.parentNode.querySelector('.invalid-feedback');
    if (existingError) {
        existingError.remove();
    }

    // Add new error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'invalid-feedback';
    errorDiv.textContent = message;
    field.parentNode.appendChild(errorDiv);
}

function clearFieldError(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return;

    field.classList.remove('is-invalid');

    const errorDiv = field.parentNode.querySelector('.invalid-feedback');
    if (errorDiv) {
        errorDiv.remove();
    }
}

function showFormErrors(errors) {
    // Create or update error summary
    let errorContainer = document.getElementById('form-errors');

    if (!errorContainer) {
        errorContainer = document.createElement('div');
        errorContainer.id = 'form-errors';
        errorContainer.className = 'alert alert-danger alert-dismissible fade show';

        // Insert at top of form
        const form = document.querySelector('form');
        form.insertBefore(errorContainer, form.firstChild);
    }

    errorContainer.innerHTML = `
        <strong>Please correct the following errors:</strong>
        <ul class="mb-0 mt-2">
            ${errors.map(error => `<li>${error}</li>`).join('')}
        </ul>
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    // Scroll to top of form
    errorContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function clearFormErrors() {
    const errorContainer = document.getElementById('form-errors');
    if (errorContainer) {
        errorContainer.remove();
    }
}

function showFormLoading(isLoading) {
    const submitButton = document.querySelector('button[type="submit"]');
    if (!submitButton) return;

    if (isLoading) {
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            Registering...
        `;
    } else {
        submitButton.disabled = false;
        submitButton.innerHTML = 'Register';
    }
}

// Auto-save form data to prevent loss (stores in sessionStorage)
function initializeAutoSave() {
    const form = document.querySelector('form');
    if (!form) return;

    const formId = 'cbc-registration-form';

    // Load saved data
    loadFormData(formId);

    // Save data on input
    form.addEventListener('input', function() {
        saveFormData(formId);
    });

    // Clear saved data on successful submission
    form.addEventListener('submit', function() {
        if (validateForm()) {
            sessionStorage.removeItem(formId);
        }
    });
}

function saveFormData(formId) {
    const form = document.querySelector('form');
    if (!form) return;

    const formData = {};
    const formElements = form.elements;

    for (let element of formElements) {
        if (element.name && element.type !== 'submit') {
            if (element.type === 'checkbox') {
                formData[element.name] = element.checked;
            } else {
                formData[element.name] = element.value;
            }
        }
    }

    try {
        sessionStorage.setItem(formId, JSON.stringify(formData));
    } catch (e) {
        // Ignore storage errors
        console.warn('Could not save form data:', e);
    }
}

function loadFormData(formId) {
    try {
        const savedData = sessionStorage.getItem(formId);
        if (!savedData) return;

        const formData = JSON.parse(savedData);
        const form = document.querySelector('form');
        if (!form) return;

        for (let [name, value] of Object.entries(formData)) {
            const element = form.elements[name];
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = value;
                } else {
                    element.value = value;
                }
            }
        }
    } catch (e) {
        // Ignore storage errors
        console.warn('Could not load form data:', e);
    }
}

function initializeParticipationTypeValidation() {
    const feederRadio = document.getElementById('feeder');
    const regularRadio = document.getElementById('regular');
    const areaDropdown = document.getElementById('preferred_area');
    const leadershipCheckbox = document.getElementById('interested_in_leadership');
    const unassignedOption = document.querySelector('option[value="UNASSIGNED"]');

    if (!feederRadio || !regularRadio || !areaDropdown || !leadershipCheckbox || !unassignedOption) {
        return;
    }

    // Handle FEEDER selection constraints
    feederRadio.addEventListener('change', function() {
        if (this.checked) {
            // Disable UNASSIGNED option
            unassignedOption.disabled = true;
            unassignedOption.style.color = '#999';
            
            // Disable and uncheck leadership checkbox
            leadershipCheckbox.disabled = true;
            leadershipCheckbox.checked = false;
            leadershipCheckbox.parentElement.style.opacity = '0.5';
            
            // If UNASSIGNED was selected, reset to empty
            if (areaDropdown.value === 'UNASSIGNED') {
                areaDropdown.value = '';
                // Clear map selection if available
                if (typeof window.highlightAreaFromDropdown === 'function') {
                    window.highlightAreaFromDropdown('');
                }
            }
        }
    });

    // Handle REGULAR selection - restore options
    regularRadio.addEventListener('change', function() {
        if (this.checked) {
            // Re-enable UNASSIGNED option
            unassignedOption.disabled = false;
            unassignedOption.style.color = '';
            
            // Re-enable leadership checkbox
            leadershipCheckbox.disabled = false;
            leadershipCheckbox.parentElement.style.opacity = '1';
        }
    });
}

// Initialize auto-save if sessionStorage is available
if (typeof(Storage) !== "undefined") {
    document.addEventListener('DOMContentLoaded', initializeAutoSave);
}