// login_script.js - Script para página de login

const API_BASE_URL = window.location.origin;

document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('login-form');
    const loginButton = document.getElementById('login-button');
    const errorMessage = document.getElementById('error-message');
    
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            if (!email || !password) {
                showError('Por favor, preencha todos os campos.');
                return;
            }
            
            // Mostrar loading
            loginButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Entrando...';
            loginButton.disabled = true;
            errorMessage.classList.add('hidden');
            
            try {
                // Fazer login no backend
                const formData = new FormData();
                formData.append('username', email);
                formData.append('password', password);
                
                const response = await fetch(`${API_BASE_URL}/auth/login`, {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Email ou senha incorretos');
                }
                
                const data = await response.json();
                
                // Salvar token
                sessionStorage.setItem('boredfy_auth_token', data.access_token);
                sessionStorage.setItem('boredfy_logged_in', 'true');
                sessionStorage.setItem('boredfy_user_email', email);
                
                // Redirecionar
                window.location.href = 'index.html';
                
            } catch (error) {
                showError(error.message);
                loginButton.innerHTML = 'Entrar';
                loginButton.disabled = false;
            }
        });
    }
    
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }
});
