// Exer Group — formulario de contacto (Formspree)
//
// IMPORTANTE: reemplazar FORMSPREE_ENDPOINT por el endpoint real antes de publicar.
// Pasos para obtenerlo (gratis, ~2 minutos):
//   1. Crear cuenta en https://formspree.io con el email candela.pilar.trigo@gmail.com
//   2. Crear un nuevo formulario ("New Form"), nombrarlo p.ej. "Exer Group — Contacto"
//   3. Formspree te da una URL del tipo https://formspree.io/f/xxxxxxxx — copiarla acá abajo
//   4. Formspree envía un email de verificación a candela.pilar.trigo@gmail.com:
//      hay que confirmarlo para que el formulario empiece a entregar mensajes
const FORMSPREE_ENDPOINT = 'https://formspree.io/f/REEMPLAZAR_CON_TU_ENDPOINT';

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('contact-form');
  if (!form) return;

  const submitBtn = form.querySelector('.form-submit');
  const submitLabel = submitBtn.querySelector('.btn-label');
  const statusSuccess = form.querySelector('[data-status="success"]');
  const statusError = form.querySelector('[data-status="error"]');

  const fieldErrors = {
    nombre: 'Ingresá tu nombre completo.',
    telefono: 'Ingresá un teléfono de contacto.',
    email: 'Ingresá un email válido.',
    servicio: 'Seleccioná el tipo de servicio.',
  };

  function setFieldError(name, message) {
    const errEl = form.querySelector(`[data-error-for="${name}"]`);
    if (errEl) errEl.textContent = message || '';
    const field = form.elements[name];
    if (field) field.classList.toggle('is-invalid', Boolean(message));
  }

  function validate() {
    let isValid = true;
    Object.keys(fieldErrors).forEach((name) => {
      const field = form.elements[name];
      setFieldError(name, '');
      if (!field) return;

      if (field.validity.valueMissing) {
        setFieldError(name, fieldErrors[name]);
        isValid = false;
      } else if (name === 'email' && field.validity.typeMismatch) {
        setFieldError(name, 'El formato del email no es válido.');
        isValid = false;
      }
    });
    return isValid;
  }

  ['nombre', 'telefono', 'email', 'servicio'].forEach((name) => {
    const field = form.elements[name];
    if (field) {
      field.addEventListener('blur', () => {
        if (field.validity.valueMissing) {
          setFieldError(name, fieldErrors[name]);
        } else if (name === 'email' && field.validity.typeMismatch) {
          setFieldError(name, 'El formato del email no es válido.');
        } else {
          setFieldError(name, '');
        }
      });
    }
  });

  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    submitLabel.innerHTML = isLoading
      ? '<span class="spinner" aria-hidden="true"></span> Enviando...'
      : 'Enviar consulta';
  }

  function showStatus(kind) {
    statusSuccess.classList.toggle('is-visible', kind === 'success');
    statusError.classList.toggle('is-visible', kind === 'error');
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    showStatus(null);

    // Honeypot: si este campo oculto viene completo, es un bot — abortamos en silencio.
    if (form.elements.company && form.elements.company.value) {
      return;
    }

    if (!validate()) {
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(FORMSPREE_ENDPOINT, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: new FormData(form),
      });

      if (response.ok) {
        showStatus('success');
        form.reset();
      } else {
        showStatus('error');
      }
    } catch (err) {
      showStatus('error');
    } finally {
      setLoading(false);
    }
  });
});
