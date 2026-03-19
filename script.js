// Smooth scrolling for navigation
document.addEventListener('DOMContentLoaded', function() {
    // Create particles
    createParticles();
    
    // Intersection Observer for fade-in animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);
    
    // Add fade-in class to step cards
    document.querySelectorAll('.step-card').forEach(card => {
        card.classList.add('fade-in');
        observer.observe(card);
    });
    
    // Add fade-in to section header
    const sectionHeader = document.querySelector('.section-header');
    if (sectionHeader) {
        sectionHeader.classList.add('fade-in');
        observer.observe(sectionHeader);
    }
    
    // Parallax effect for hero section
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const hero = document.querySelector('.hero');
        const heroContent = document.querySelector('.hero-content');
        
        if (hero && heroContent) {
            hero.style.transform = `translateY(${scrolled * 0.5}px)`;
            heroContent.style.transform = `translateY(${scrolled * 0.3}px)`;
        }
    });
    
    // Neon glow effect on mouse move
    document.addEventListener('mousemove', (e) => {
        const cards = document.querySelectorAll('.step-card');
        const mouseX = e.clientX;
        const mouseY = e.clientY;
        
        cards.forEach(card => {
            const rect = card.getBoundingClientRect();
            const cardX = rect.left + rect.width / 2;
            const cardY = rect.top + rect.height / 2;
            
            const distance = Math.sqrt(
                Math.pow(mouseX - cardX, 2) + Math.pow(mouseY - cardY, 2)
            );
            
            if (distance < 200) {
                const intensity = 1 - (distance / 200);
                card.style.boxShadow = `
                    0 20px 40px rgba(255, 0, 255, ${0.3 * intensity}),
                    0 0 ${30 * intensity}px rgba(255, 0, 255, ${0.2 * intensity})
                `;
            }
        });
    });
    
    // Smooth scroll for any navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});

// Create floating particles
function createParticles() {
    const particlesContainer = document.createElement('div');
    particlesContainer.className = 'particles';
    document.body.appendChild(particlesContainer);
    
    const particleCount = 50;
    
    for (let i = 0; i < particleCount; i++) {
        createParticle(particlesContainer);
    }
}

function createParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'particle';
    
    // Random starting position
    particle.style.left = Math.random() * 100 + '%';
    particle.style.animationDelay = Math.random() * 10 + 's';
    particle.style.animationDuration = (10 + Math.random() * 10) + 's';
    
    // Random color
    const colors = ['#ff00ff', '#00ffff', '#ff00aa', '#00ff00'];
    particle.style.background = colors[Math.floor(Math.random() * colors.length)];
    particle.style.boxShadow = `0 0 6px ${particle.style.background}`;
    
    container.appendChild(particle);
    
    // Remove particle after animation completes and create new one
    particle.addEventListener('animationend', () => {
        particle.remove();
        createParticle(container);
    });
}

// Add typing effect to hero title
function typeWriter() {
    const title = document.querySelector('.hero-title');
    if (!title) return;
    
    const neonText = title.querySelector('.neon-text');
    if (!neonText) return;
    
    const text = neonText.textContent;
    neonText.textContent = '';
    
    let i = 0;
    function type() {
        if (i < text.length) {
            neonText.textContent += text.charAt(i);
            i++;
            setTimeout(type, 50);
        }
    }
    
    setTimeout(type, 500);
}

// Initialize typing effect
window.addEventListener('load', typeWriter);

// Add glitch effect to neon text
function addGlitchEffect() {
    const neonTexts = document.querySelectorAll('.neon-text');
    
    neonTexts.forEach(text => {
        setInterval(() => {
            if (Math.random() > 0.95) {
                text.style.animation = 'none';
                setTimeout(() => {
                    text.style.animation = '';
                }, 100);
            }
        }, 3000);
    });
}

addGlitchEffect();

// Easter egg: Konami code
let konamiCode = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
let konamiIndex = 0;

document.addEventListener('keydown', (e) => {
    if (e.key === konamiCode[konamiIndex]) {
        konamiIndex++;
        if (konamiIndex === konamiCode.length) {
            activateEasterEgg();
            konamiIndex = 0;
        }
    } else {
        konamiIndex = 0;
    }
});

function activateEasterEgg() {
    document.body.style.animation = 'rainbow 5s linear';
    setTimeout(() => {
        document.body.style.animation = '';
    }, 5000);
}

// Add rainbow animation
const style = document.createElement('style');
style.textContent = `
    @keyframes rainbow {
        0% { filter: hue-rotate(0deg); }
        100% { filter: hue-rotate(360deg); }
    }
`;
document.head.appendChild(style);
