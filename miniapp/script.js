// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;

// Expand the app to full height
tg.expand();

// Apply Telegram theme
if (tg.themeParams) {
    document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#000000');
    document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color || '#999999');
    document.documentElement.style.setProperty('--tg-theme-link-color', tg.themeParams.link_color || '#2481cc');
    document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#2481cc');
    document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f0f0f0');
}

// Apply dark theme if Telegram is in dark mode
if (tg.colorScheme === 'dark') {
    document.body.classList.add('theme-dark');
}

// Navigation buttons
const navBtns = document.querySelectorAll('.nav-btn');
const tabs = document.querySelectorAll('.tab');

// Function to switch tabs with haptic feedback
function switchTab(tabName) {
    // Haptic feedback - impact
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
    }

    // Remove active class from all buttons and tabs
    navBtns.forEach(btn => btn.classList.remove('active'));
    tabs.forEach(tab => tab.classList.remove('active'));

    // Add active class to clicked button and corresponding tab
    const activeBtn = document.querySelector(`[data-tab="${tabName}"]`);
    const activeTab = document.getElementById(`tab-${tabName}`);

    if (activeBtn && activeTab) {
        activeBtn.classList.add('active');
        activeTab.classList.add('active');
    }
}

// Add click event listeners to navigation buttons
navBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
        const tabName = btn.getAttribute('data-tab');
        switchTab(tabName);
    });
});

// Add haptic feedback to all interactive elements
function addHapticFeedback() {
    // Cards
    const cards = document.querySelectorAll('.card, .price-card, .instruction-step, .referral-card, .stat-item, .settings-item');
    cards.forEach(card => {
        card.addEventListener('click', () => {
            if (tg.HapticFeedback) {
                tg.HapticFeedback.impactOccurred('light');
            }
        });
    });

    // Buttons
    const buttons = document.querySelectorAll('.copy-btn, .settings-toggle');
    buttons.forEach(button => {
        button.addEventListener('click', () => {
            if (tg.HapticFeedback) {
                tg.HapticFeedback.impactOccurred('medium');
            }
        });
    });
}

// Initialize haptic feedback
addHapticFeedback();

// Copy referral link functionality
const copyBtn = document.querySelector('.copy-btn');
if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
        const referralLink = document.querySelector('.referral-link').textContent;
        
        try {
            await navigator.clipboard.writeText(referralLink);
            
            // Haptic feedback for success
            if (tg.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred('success');
            }
            
            // Show success message
            copyBtn.textContent = 'Скопировано!';
            setTimeout(() => {
                copyBtn.textContent = 'Копировать';
            }, 2000);
        } catch (err) {
            // Haptic feedback for error
            if (tg.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred('error');
            }
        }
    });
}

// Settings toggle functionality
const settingsToggles = document.querySelectorAll('.settings-toggle');
settingsToggles.forEach(toggle => {
    toggle.addEventListener('click', () => {
        toggle.classList.toggle('active');
        
        // Haptic feedback
        if (tg.HapticFeedback) {
            tg.HapticFeedback.impactOccurred('light');
        }
    });
});

// Price card selection
const priceCards = document.querySelectorAll('.price-card');
priceCards.forEach(card => {
    card.addEventListener('click', () => {
        // Remove active state from all cards
        priceCards.forEach(c => c.style.transform = 'scale(1)');
        
        // Add active state to clicked card
        card.style.transform = 'scale(1.05)';
        
        // Haptic feedback
        if (tg.HapticFeedback) {
            tg.HapticFeedback.impactOccurred('medium');
        }
        
        // Show selection alert (in real app, this would open payment)
        if (tg.showAlert) {
            tg.showAlert('Выбран план: ' + card.querySelector('.price-duration').textContent);
        }
    });
});

// Handle back button (if needed)
if (tg.BackButton) {
    tg.BackButton.show();
    tg.BackButton.onClick(() => {
        if (tg.HapticFeedback) {
            tg.HapticFeedback.impactOccurred('light');
        }
        // Handle back navigation
        const activeTab = document.querySelector('.tab.active');
        if (activeTab && activeTab.id !== 'tab-main') {
            switchTab('main');
        } else {
            tg.close();
        }
    });
}

// Handle main button (if needed)
if (tg.MainButton) {
    tg.MainButton.setText('Открыть бота');
    tg.MainButton.show();
    tg.MainButton.onClick(() => {
        if (tg.HapticFeedback) {
            tg.HapticFeedback.impactOccurred('medium');
        }
        tg.openTelegramLink('https://t.me/your_bot');
    });
}

// Ready - tell Telegram that the app is ready
tg.ready();

// Log initialization
console.log('Telegram Mini App initialized');
console.log('Theme:', tg.colorScheme);
console.log('Version:', tg.version);
console.log('Platform:', tg.platform);
