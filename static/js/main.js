// Mobile Menu Toggle
const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
const navLinks = document.querySelector('.nav-links');
const navButtons = document.querySelector('.nav-buttons');

if (mobileMenuToggle) {
    mobileMenuToggle.addEventListener('click', () => {
        navLinks.classList.toggle('active');
        navButtons.classList.toggle('active');
        
        const icon = mobileMenuToggle.querySelector('i');
        if (icon.classList.contains('fa-bars')) {
            icon.classList.remove('fa-bars');
            icon.classList.add('fa-times');
        } else {
            icon.classList.remove('fa-times');
            icon.classList.add('fa-bars');
        }
    });
}

// Smooth Scrolling for Navigation Links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        
        // Only prevent default for hash links, not for regular links
        if (href !== '#' && href.startsWith('#')) {
            e.preventDefault();
            
            const target = document.querySelector(href);
            if (target) {
                const navbarHeight = document.querySelector('.navbar').offsetHeight;
                const targetPosition = target.offsetTop - navbarHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
                
                // Close mobile menu if open
                if (navLinks.classList.contains('active')) {
                    navLinks.classList.remove('active');
                    navButtons.classList.remove('active');
                    const icon = mobileMenuToggle.querySelector('i');
                    icon.classList.remove('fa-times');
                    icon.classList.add('fa-bars');
                }
            }
        }
    });
});

// Navbar Scroll Effect
let lastScroll = 0;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll <= 0) {
        navbar.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
    }
    
    // Hide/show navbar on scroll
    if (currentScroll > lastScroll && currentScroll > 100) {
        navbar.style.transform = 'translateY(-100%)';
    } else {
        navbar.style.transform = 'translateY(0)';
    }
    
    lastScroll = currentScroll;
});

// Active Navigation Link on Scroll
const sections = document.querySelectorAll('section[id]');
const navLinksAll = document.querySelectorAll('.nav-links a[href^="#"]');

window.addEventListener('scroll', () => {
    let current = '';
    
    sections.forEach(section => {
        const sectionTop = section.offsetTop;
        const sectionHeight = section.clientHeight;
        
        if (window.pageYOffset >= sectionTop - 200) {
            current = section.getAttribute('id');
        }
    });
    
    navLinksAll.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${current}`) {
            link.classList.add('active');
        }
    });
});

// Counter Animation for Statistics
const observerOptions = {
    threshold: 0.5,
    rootMargin: '0px'
};

const animateCounter = (element, target, duration = 2000) => {
    let current = 0;
    const increment = target / (duration / 16); // 60fps
    const isDecimal = target.toString().includes('.');
    
    const updateCounter = () => {
        current += increment;
        if (current < target) {
            element.textContent = isDecimal ? current.toFixed(1) : Math.floor(current);
            requestAnimationFrame(updateCounter);
        } else {
            element.textContent = target;
        }
    };
    
    updateCounter();
};

const counters = document.querySelectorAll('.stat-item h3, .impact-card h3');
const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.classList.contains('counted')) {
            entry.target.classList.add('counted');
            const text = entry.target.textContent;
            const number = parseFloat(text.replace(/[^0-9.]/g, ''));
            
            if (!isNaN(number)) {
                entry.target.textContent = '0';
                animateCounter(entry.target, number);
                
                // Add back any suffix (like +, kg, etc.)
                setTimeout(() => {
                    entry.target.textContent = text;
                }, 2000);
            }
        }
    });
}, observerOptions);

counters.forEach(counter => counterObserver.observe(counter));

// Scroll Reveal Animation
const revealOptions = {
    threshold: 0.15,
    rootMargin: '0px'
};

const revealOnScroll = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
        }
    });
}, revealOptions);

// Add reveal class to elements
const revealElements = document.querySelectorAll('.feature-card, .campaign-card, .impact-card, .about-text, .about-image');
revealElements.forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(30px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    revealOnScroll.observe(el);
});

// Add revealed styles
const style = document.createElement('style');
style.textContent = `
    .revealed {
        opacity: 1 !important;
        transform: translateY(0) !important;
    }
`;
document.head.appendChild(style);

// Form Validation (for future login/register pages)
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const email = form.querySelector('input[type="email"]');
        const password = form.querySelector('input[type="password"]');
        
        let isValid = true;
        
        // Clear previous errors
        document.querySelectorAll('.error-message').forEach(el => el.remove());
        
        // Email validation
        if (email && !validateEmail(email.value)) {
            showError(email, 'Please enter a valid email address');
            isValid = false;
        }
        
        // Password validation
        if (password && password.value.length < 6) {
            showError(password, 'Password must be at least 6 characters');
            isValid = false;
        }
        
        if (isValid) {
            form.submit();
        }
    });
}

function showError(input, message) {
    const error = document.createElement('div');
    error.className = 'error-message';
    error.style.color = '#ef4444';
    error.style.fontSize = '0.875rem';
    error.style.marginTop = '0.25rem';
    error.textContent = message;
    input.parentElement.appendChild(error);
    input.style.borderColor = '#ef4444';
}

// Campaign Search and Filter (for campaigns page)
function initCampaignFilters() {
    const searchInput = document.getElementById('campaign-search');
    const categoryFilter = document.getElementById('category-filter');
    const locationFilter = document.getElementById('location-filter');
    
    if (searchInput || categoryFilter || locationFilter) {
        const filterCampaigns = () => {
            const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
            const category = categoryFilter ? categoryFilter.value : '';
            const location = locationFilter ? locationFilter.value : '';
            
            const campaigns = document.querySelectorAll('.campaign-card');
            
            campaigns.forEach(campaign => {
                const title = campaign.querySelector('h3').textContent.toLowerCase();
                const campaignCategory = campaign.dataset.category || '';
                const campaignLocation = campaign.dataset.location || '';
                
                const matchesSearch = title.includes(searchTerm);
                const matchesCategory = !category || campaignCategory === category;
                const matchesLocation = !location || campaignLocation === location;
                
                if (matchesSearch && matchesCategory && matchesLocation) {
                    campaign.style.display = 'block';
                    setTimeout(() => {
                        campaign.style.opacity = '1';
                        campaign.style.transform = 'translateY(0)';
                    }, 10);
                } else {
                    campaign.style.opacity = '0';
                    campaign.style.transform = 'translateY(20px)';
                    setTimeout(() => {
                        campaign.style.display = 'none';
                    }, 300);
                }
            });
        };
        
        if (searchInput) searchInput.addEventListener('input', filterCampaigns);
        if (categoryFilter) categoryFilter.addEventListener('change', filterCampaigns);
        if (locationFilter) locationFilter.addEventListener('change', filterCampaigns);
    }
}

// Load more campaigns functionality
function initLoadMore() {
    const loadMoreBtn = document.getElementById('load-more-campaigns');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', async () => {
            loadMoreBtn.disabled = true;
            loadMoreBtn.textContent = 'Loading...';
            
            try {
                // Fetch more campaigns from backend
                const response = await fetch('/api/campaigns?offset=' + document.querySelectorAll('.campaign-card').length);
                const data = await response.json();
                
                // Add campaigns to page
                const campaignsGrid = document.querySelector('.campaigns-grid');
                data.campaigns.forEach(campaign => {
                    const card = createCampaignCard(campaign);
                    campaignsGrid.appendChild(card);
                });
                
                if (!data.has_more) {
                    loadMoreBtn.style.display = 'none';
                }
            } catch (error) {
                console.error('Error loading campaigns:', error);
                alert('Failed to load more campaigns. Please try again.');
            } finally {
                loadMoreBtn.disabled = false;
                loadMoreBtn.textContent = 'Load More';
            }
        });
    }
}

// Create campaign card dynamically
function createCampaignCard(campaign) {
    const card = document.createElement('div');
    card.className = 'campaign-card';
    card.dataset.category = campaign.category;
    card.dataset.location = campaign.location;
    
    card.innerHTML = `
        <div class="campaign-image">
            <img src="${campaign.image || 'static/images/default-campaign.jpg'}" alt="${campaign.title}">
            ${campaign.featured ? '<div class="campaign-badge">Featured</div>' : ''}
        </div>
        <div class="campaign-content">
            <div class="campaign-meta">
                <span><i class="fas fa-calendar"></i> ${campaign.date}</span>
                <span><i class="fas fa-map-marker-alt"></i> ${campaign.location}</span>
            </div>
            <h3>${campaign.title}</h3>
            <p>${campaign.description}</p>
            <div class="campaign-footer">
                <div class="campaign-volunteers">
                    <i class="fas fa-users"></i>
                    <span>${campaign.volunteers_joined}/${campaign.volunteers_needed} Volunteers</span>
                </div>
                <a href="/campaigns/${campaign.id}" class="btn btn-small btn-primary">Join Now</a>
            </div>
        </div>
    `;
    
    return card;
}

// Notification system
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        padding: 1rem 1.5rem;
        background-color: ${type === 'success' ? '#22c55e' : '#ef4444'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add notification animations
const notificationStyle = document.createElement('style');
notificationStyle.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(notificationStyle);

// Initialize all functions when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initCampaignFilters();
    initLoadMore();
    
    // Check for success/error messages in URL params
    const urlParams = new URLSearchParams(window.location.search);
    const message = urlParams.get('message');
    const type = urlParams.get('type');
    
    if (message) {
        showNotification(decodeURIComponent(message), type || 'success');
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

// Export functions for use in other scripts
window.GreenSpark = {
    showNotification,
    validateEmail,
    createCampaignCard
};