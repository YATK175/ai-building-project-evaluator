const { createApp, ref, computed, onMounted } = Vue;

function getOrCreateBrowserId() {
    const key = 'realtyvision_browser_id';
    let id = localStorage.getItem(key);
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem(key, id);
    }
    return id;
}

const MODE_LABELS = {
    full: 'AI-оцінка повна',
    full_with_cached_prices: 'Ціни з кешу',
    degraded: 'AI обмежений',
    offline: 'Без AI',
    checking: 'Перевірка...',
};

const SOURCE_NAMES = {
    domria_live: 'DOM.RIA',
    cache: 'DOM.RIA (кеш)',
    cache_stale: 'DOM.RIA (застарілий кеш)',
    fallback: 'статичний довідник',
};

createApp({
    setup() {
        const currentPage = ref('evaluate');
        const browserId = ref(getOrCreateBrowserId());
        const currentMode = ref('checking');
        const regions = ref([]);
        const currentYear = new Date().getFullYear();

        const form = ref({
            photos: [],
            photoPreviews: [],
            stateId: null,
            cityId: null,
            cities: [],
            realtyType: 'apartment',
            roomsCount: 2,
            floor: null,
            totalFloors: null,
            yearBuilt: null,
            userArea: null,
            userDescription: '',
        });

        const isDragging = ref(false);
        const isLoading = ref(false);
        const evaluation = ref(null);
        const photoIds = ref([]);
        const evalError = ref(null);
        const isSaved = ref(false);

        const history = ref([]);
        const historyLoading = ref(false);
        const selectedItem = ref(null);

        const loadingSteps = ref([
            { id: 'upload', label: 'Фото завантажено', done: false, active: false },
            { id: 'vision', label: 'Аналіз фото через AI...', done: false, active: false },
            { id: 'prices', label: 'Отримання ринкових цін...', done: false, active: false },
            { id: 'calc', label: 'Розрахунок коригувань...', done: false, active: false },
            { id: 'explain', label: 'Генерація пояснення...', done: false, active: false },
        ]);

        let progressTimer = null;

        const modeLabel = computed(() => MODE_LABELS[currentMode.value] || 'Перевірка...');
        const canSubmit = computed(() =>
            form.value.photos.length > 0 &&
            form.value.stateId !== null &&
            form.value.cityId !== null
        );

        async function checkHealth() {
            try {
                const r = await fetch('/api/health');
                const data = await r.json();
                currentMode.value = data.current_mode || 'offline';
            } catch {
                currentMode.value = 'offline';
            }
        }

        async function loadRegions() {
            try {
                const r = await fetch('/api/regions');
                regions.value = await r.json();
            } catch (e) {
                console.error('Помилка завантаження регіонів:', e);
            }
        }

        async function loadCities() {
            form.value.cityId = null;
            form.value.cities = [];
            if (!form.value.stateId) return;
            try {
                const r = await fetch(`/api/cities/${form.value.stateId}`);
                form.value.cities = await r.json();
                if (form.value.cities.length > 0) {
                    form.value.cityId = form.value.cities[0].city_id;
                }
            } catch (e) {
                console.error('Помилка завантаження міст:', e);
            }
        }

        function onFileSelect(e) {
            addFiles(Array.from(e.target.files));
            e.target.value = '';
        }

        function onDrop(e) {
            isDragging.value = false;
            addFiles(Array.from(e.dataTransfer.files));
        }

        function addFiles(files) {
            const allowed = ['image/jpeg', 'image/png', 'image/webp'];
            for (const file of files) {
                if (!allowed.includes(file.type)) continue;
                if (form.value.photos.length >= 10) break;
                form.value.photos.push(file);
                const reader = new FileReader();
                reader.onload = (ev) => form.value.photoPreviews.push(ev.target.result);
                reader.readAsDataURL(file);
            }
        }

        function removePhoto(idx) {
            form.value.photos.splice(idx, 1);
            form.value.photoPreviews.splice(idx, 1);
        }

        function startProgress() {
            loadingSteps.value.forEach(s => { s.done = false; s.active = false; });
            let step = 0;
            const delays = [300, 800, 12000, 2000, 4000];
            function next() {
                if (step < loadingSteps.value.length) {
                    if (step > 0) loadingSteps.value[step - 1].done = true;
                    loadingSteps.value[step].active = true;
                    progressTimer = setTimeout(() => {
                        step++;
                        next();
                    }, delays[step] || 2000);
                }
            }
            next();
        }

        function stopProgress() {
            if (progressTimer) {
                clearTimeout(progressTimer);
                progressTimer = null;
            }
            loadingSteps.value.forEach(s => { s.done = true; s.active = false; });
        }

        async function submitEvaluation() {
            if (!canSubmit.value || isLoading.value) return;
            isLoading.value = true;
            evaluation.value = null;
            evalError.value = null;
            isSaved.value = false;
            photoIds.value = [];
            startProgress();

            const fd = new FormData();
            form.value.photos.forEach(f => fd.append('photos[]', f));
            fd.append('state_id', form.value.stateId);
            fd.append('city_id', form.value.cityId);
            fd.append('realty_type', form.value.realtyType);
            fd.append('rooms_count', form.value.roomsCount);
            if (form.value.floor) fd.append('floor', form.value.floor);
            if (form.value.totalFloors) fd.append('total_floors', form.value.totalFloors);
            if (form.value.yearBuilt) fd.append('year_built', form.value.yearBuilt);
            if (form.value.userArea) fd.append('user_area', form.value.userArea);
            if (form.value.userDescription) fd.append('user_description', form.value.userDescription);

            try {
                const resp = await fetch('/api/evaluate', { method: 'POST', body: fd });
                stopProgress();
                const data = await resp.json();
                if (!resp.ok) {
                    evalError.value = data.error || 'Невідома помилка';
                } else {
                    evaluation.value = data.evaluation;
                    photoIds.value = data.photo_ids || [];
                    currentMode.value = data.evaluation.mode;
                }
            } catch (e) {
                stopProgress();
                evalError.value = 'Помилка мережі: ' + e.message;
            } finally {
                isLoading.value = false;
            }
        }

        async function saveEvaluation() {
            if (!evaluation.value || isSaved.value) return;
            try {
                const resp = await fetch('/api/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        browser_id: browserId.value,
                        evaluation: evaluation.value,
                        photo_ids: photoIds.value,
                        input: {},
                    }),
                });
                if (resp.ok) {
                    isSaved.value = true;
                }
            } catch (e) {
                console.error('Помилка збереження:', e);
            }
        }

        function resetEvaluation() {
            evaluation.value = null;
            evalError.value = null;
            isSaved.value = false;
            photoIds.value = [];
            form.value.photos = [];
            form.value.photoPreviews = [];
        }

        async function goHistory() {
            currentPage.value = 'history';
            await loadHistory();
        }

        async function loadHistory() {
            historyLoading.value = true;
            try {
                const r = await fetch(`/api/history?browser_id=${encodeURIComponent(browserId.value)}`);
                history.value = await r.json();
            } catch {
                history.value = [];
            } finally {
                historyLoading.value = false;
            }
        }

        async function openHistoryItem(id) {
            try {
                const r = await fetch(`/api/history/${id}?browser_id=${encodeURIComponent(browserId.value)}`);
                if (r.ok) selectedItem.value = await r.json();
            } catch (e) {
                console.error('Помилка відкриття запису:', e);
            }
        }

        async function deleteHistoryItem(id) {
            if (!confirm('Видалити цю оцінку?')) return;
            try {
                await fetch(`/api/history/${id}?browser_id=${encodeURIComponent(browserId.value)}`, {
                    method: 'DELETE',
                });
                history.value = history.value.filter(h => h.id !== id);
            } catch (e) {
                console.error('Помилка видалення:', e);
            }
        }

        function formatNum(n) {
            if (n == null) return '—';
            return Number(n).toLocaleString('uk-UA');
        }

        function formatDate(iso) {
            if (!iso) return '';
            try {
                const d = new Date(iso);
                return d.toLocaleString('uk-UA', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
            } catch {
                return iso;
            }
        }

        function sourceName(src) {
            return SOURCE_NAMES[src] || src;
        }

        function coefClass(val) {
            if (val == null) return 'coef-neutral';
            const v = parseFloat(val);
            if (v > 1.01) return 'coef-positive';
            if (v < 0.99) return 'coef-negative';
            return 'coef-neutral';
        }

        onMounted(async () => {
            await Promise.all([checkHealth(), loadRegions()]);
        });

        return {
            currentPage, currentMode, modeLabel, regions, currentYear,
            form, isDragging, isLoading, loadingSteps,
            evaluation, evalError, isSaved, photoIds,
            history, historyLoading, selectedItem,
            canSubmit,
            loadCities, onFileSelect, onDrop, removePhoto,
            submitEvaluation, saveEvaluation, resetEvaluation,
            goHistory, openHistoryItem, deleteHistoryItem,
            formatNum, formatDate, sourceName, coefClass,
        };
    },
}).mount('#app');
