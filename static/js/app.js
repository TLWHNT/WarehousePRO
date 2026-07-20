// Переключение темы
document.addEventListener('DOMContentLoaded', function() {
    const themeSwitch = document.getElementById('themeSwitch');
    const currentTheme = localStorage.getItem('theme') || 'light';
    
    document.documentElement.setAttribute('data-theme', currentTheme);
    updateThemeIcon(currentTheme);
    
    if (themeSwitch) {
        themeSwitch.addEventListener('click', function() {
            const theme = document.documentElement.getAttribute('data-theme');
            const newTheme = theme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
        });
    }
});

function updateThemeIcon(theme) {
    const icon = document.querySelector('#themeSwitch i');
    if (icon) {
        icon.className = theme === 'light' ? 'bi bi-moon' : 'bi bi-sun';
    }
}

// Превью изображения при загрузке
function previewImage(input, previewId) {
    const preview = document.getElementById(previewId);
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
            preview.style.animation = 'fadeIn 0.4s ease-out';
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// Подтверждение удаления
function confirmDelete(message) {
    return confirm(message || 'Вы уверены?');
}

// Тултипы для графиков
const chartOptions = {
    responsive: true,
    plugins: {
        legend: {
            position: 'bottom',
            labels: {
                padding: 20,
                font: { size: 14 }
            }
        },
        tooltip: {
            backgroundColor: 'rgba(0,0,0,0.8)',
            padding: 12,
            titleFont: { size: 16 },
            bodyFont: { size: 14 },
            cornerRadius: 8
        }
    },
    animation: {
        duration: 1000,
        easing: 'easeOutQuart'
    }
};