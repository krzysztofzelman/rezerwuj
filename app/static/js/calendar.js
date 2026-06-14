/**
 * Napraw Mnie — Kalendarz i system rezerwacji (frontend)
 *
 * Obsługuje:
 * - Inicjalizację Flatpickr z dostępnymi datami
 * - Pobieranie slotów czasowych z API
 * - Wybór slotu i wyświetlanie formularza
 * - Wysyłanie rezerwacji AJAX-em
 * - Obsługę płatności (modal Stripe)
 */

(function () {
    'use strict';

    // === Stan ===
    const state = {
        selectedDate: null,
        selectedTime: null,
        isLoadingSlots: false,
        isSubmitting: false,
    };

    // === Elementy DOM ===
    const $ = (sel) => document.querySelector(sel);
    const slotsContainer = document.getElementById('slots-container');
    const bookingForm = document.getElementById('booking-form');
    const bookingFormInner = document.getElementById('booking-form-inner');
    const bookingSuccess = document.getElementById('booking-success');
    const successMessage = document.getElementById('success-message');
    const paymentInfo = document.getElementById('payment-info');
    const formDate = document.getElementById('form-date');
    const formTime = document.getElementById('form-time');
    const bookBtn = document.getElementById('book-btn');
    const paymentModalEl = document.getElementById('paymentModal');

    let paymentModal = null;
    if (paymentModalEl && typeof bootstrap !== 'undefined') {
        paymentModal = new bootstrap.Modal(paymentModalEl);
    }

    // === Konfiguracja ===
    const slug = typeof CONFIG !== 'undefined' ? CONFIG.slug : '';
    const serviceDuration = typeof CONFIG !== 'undefined' ? CONFIG.duration : 60;
    const requireDeposit = typeof CONFIG !== 'undefined' ? CONFIG.requireDeposit : false;

    if (!slug) {
        console.error('Brak CONFIG.slug – kalendarz nie zostanie uruchomiony');
        return;
    }

    // ============================================================
    // 1. Flatpickr — kalendarz
    // ============================================================

    // Ustaw zakres dat
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const maxDate = new Date(today);
    maxDate.setDate(maxDate.getDate() + 60);

    const flatpickrInstance = flatpickr('#calendar', {
        locale: 'pl',
        inline: true,
        minDate: today,
        maxDate: maxDate,
        disableMobile: true,
        dateFormat: 'Y-m-d',
        onChange: function (selectedDates, dateStr) {
            onDateSelected(dateStr);
        },
        onDayCreate: function (dObj, dStr, fp, dayElem) {
            // Zaznaczymy dostępność po załadowaniu
            checkDayAvailability(dayElem);
        },
    });

    // ============================================================
    // 2. Sprawdzanie dostępności dni
    // ============================================================

    async function checkDayAvailability(dayElem) {
        const dateStr = dayElem.dateObj
            ? `${dayElem.dateObj.getFullYear()}-${String(dayElem.dateObj.getMonth() + 1).padStart(2, '0')}-${String(dayElem.dateObj.getDate()).padStart(2, '0')}`
            : null;
        if (!dateStr) return;

        // Pomijamy dni z przeszłości
        if (dayElem.dateObj < today) return;

        try {
            const resp = await fetch(`/api/${slug}/slots?date=${dateStr}`);
            const data = await resp.json();
            if (data.slots && data.slots.length > 0) {
                dayElem.classList.add('available');
                dayElem.title = `Dostępne terminy: ${data.slots.length}`;
            }
        } catch (e) {
            // ignoruj błędy dla poszczególnych dni
        }
    }

    // Ładuj dostępność dla wszystkich widocznych dni
    function loadAllVisibleDays() {
        const days = document.querySelectorAll('.flatpickr-day:not(.flatpickr-day.prevMonthDay):not(.flatpickr-day.nextMonthDay)');
        days.forEach(checkDayAvailability);
    }

    // Po zmianie miesiąca
    document.querySelector('.flatpickr-calendar')?.addEventListener('focus', function () {
        setTimeout(loadAllVisibleDays, 100);
    }, true);

    // ============================================================
    // 3. Obsługa wyboru daty
    // ============================================================

    async function onDateSelected(dateStr) {
        state.selectedDate = dateStr;
        state.selectedTime = null;
        bookingForm.classList.add('d-none');
        bookingSuccess.classList.add('d-none');

        // Pokaż ładowanie
        slotsContainer.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border text-primary spinner-border-sm" role="status"></div>
                <p class="mt-2 small text-muted">Sprawdzanie dostępnych terminów...</p>
            </div>
        `;

        state.isLoadingSlots = true;

        try {
            const resp = await fetch(`/api/${slug}/slots?date=${dateStr}`);
            const data = await resp.json();

            state.isLoadingSlots = false;

            if (data.slots && data.slots.length > 0) {
                renderSlots(data.slots);
            } else {
                slotsContainer.innerHTML = `
                    <div class="text-center py-4 text-muted">
                        <i class="bi bi-calendar-x display-6"></i>
                        <p class="mt-2">Brak dostępnych terminów w tym dniu</p>
                        <p class="small">Wybierz inną datę</p>
                    </div>
                `;
            }
        } catch (e) {
            state.isLoadingSlots = false;
            slotsContainer.innerHTML = `
                <div class="text-center py-4 text-danger">
                    <i class="bi bi-exclamation-triangle display-6"></i>
                    <p class="mt-2">Błąd ładowania terminów</p>
                    <p class="small">Spróbuj ponownie później</p>
                </div>
            `;
        }
    }

    // ============================================================
    // 4. Renderowanie slotów
    // ============================================================

    function renderSlots(slots) {
        let html = '<div class="row g-2">';
        slots.forEach((slot) => {
            html += `
                <div class="col-6 col-md-4">
                    <button type="button" class="slot-btn" data-time="${slot}" onclick="window.selectSlot('${slot}')">
                        ${slot}
                    </button>
                </div>
            `;
        });
        html += '</div>';
        slotsContainer.innerHTML = html;
    }

    // Wybór slotu (globalnie, bo wywoływane z onclick)
    window.selectSlot = function (time) {
        state.selectedTime = time;

        // Odznacz wszystkie
        document.querySelectorAll('.slot-btn').forEach((btn) => {
            btn.classList.remove('selected');
        });

        // Zaznacz wybrany
        const selectedBtn = document.querySelector(`.slot-btn[data-time="${time}"]`);
        if (selectedBtn) {
            selectedBtn.classList.add('selected');
        }

        // Pokaż formularz
        formDate.value = state.selectedDate;
        formTime.value = time;
        bookingForm.classList.remove('d-none');
        bookingSuccess.classList.add('d-none');

        // Przewiń do formularza
        bookingForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };

    // ============================================================
    // 5. Wysyłanie rezerwacji
    // ============================================================

    bookingFormInner.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (state.isSubmitting) return;

        // Walidacja HTML5
        if (!this.checkValidity()) {
            this.classList.add('was-validated');
            return;
        }

        state.isSubmitting = true;
        bookBtn.disabled = true;
        bookBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Rezerwowanie...';

        const formData = {
            date: formDate.value,
            time: formTime.value,
            client_name: document.getElementById('client_name').value.trim(),
            client_surname: document.getElementById('client_surname').value.trim(),
            client_phone: document.getElementById('client_phone').value.trim(),
            client_email: document.getElementById('client_email').value.trim(),
        };

        // Dodaj token reCAPTCHA jeśli istnieje
        const recaptchaResp = document.getElementById('g-recaptcha-response');
        if (recaptchaResp && recaptchaResp.value) {
            formData.g_recaptcha_response = recaptchaResp.value;
        }

        try {
            const resp = await fetch(`/api/${slug}/book`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData),
            });

            const data = await resp.json();

            if (data.success) {
                bookingForm.classList.add('d-none');
                bookingSuccess.classList.remove('d-none');
                successMessage.innerHTML =
                    `Rezerwacja u <strong>${data.provider_name}</strong> na dzień <strong>${data.date}</strong> o godzinie <strong>${data.time}</strong> została przyjęta. ` +
                    `Potwierdzenie zostało wysłane SMS-em.`;

                if (data.require_payment && data.payment_url) {
                    paymentInfo.classList.remove('d-none');
                    paymentInfo.innerHTML = `Wymagana jest zaliczka. <a href="${data.payment_url}" class="alert-link">Przejdź do płatności</a>.`;

                    // Pokaż modal płatności
                    const payLink = document.getElementById('payment-link');
                    if (payLink) {
                        payLink.href = data.payment_url;
                    }
                    if (paymentModal) {
                        paymentModal.show();
                    }
                }
            } else {
                alert(data.error || 'Wystąpił błąd podczas rezerwacji. Spróbuj ponownie.');
            }
        } catch (e) {
            alert('Wystąpił błąd połączenia. Sprawdź swoje połączenie internetowe i spróbuj ponownie.');
        } finally {
            state.isSubmitting = false;
            bookBtn.disabled = false;
            bookBtn.innerHTML = '<i class="bi bi-calendar-check"></i> Zgłoś do naprawy';
        }
    });

    // ============================================================
    // 6. Inicjalizacja — po załadowaniu strony
    // ============================================================

    // Odśwież dostępność dni po chwili (po renderze Flatpickr)
    setTimeout(loadAllVisibleDays, 500);
    setTimeout(loadAllVisibleDays, 1500);

    console.log('📅 Napraw Mnie — kalendarz zainicjalizowany');
})();
