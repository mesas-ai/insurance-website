"""
Insurance Comparator API
Flask backend for the insurance comparison application
"""

# CRITICAL: Load environment variables FIRST before any other imports
# This ensures DB connection can read MySQL credentials from .env
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_from_directory, send_file, session, redirect, url_for
from flask_cors import CORS
import os
from datetime import datetime

from comparison_service import get_all_quotes, compare_insurance
from scrapers import SCRAPER_FUNCTIONS, shutdown_rma_manager
from database.models import init_database, DatabaseManager
from auth import init_admin_user, login_required, admin_required, api_key_or_login_required, get_current_user, login_user, logout_user
import atexit

app = Flask(__name__, static_folder='static')

# Set secret key for sessions
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Enable CORS - Allow any website to hit this API
CORS(app,
     resources={
         r"/api/*": {
             "origins": "*",
             "methods": ["GET", "POST", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"],
             "expose_headers": ["Content-Type"],
             "max_age": 3600
         }
     },
     supports_credentials=True
)

# Initialize database and admin user
init_database()
init_admin_user()

# Register cleanup for RMA browser manager on app shutdown
atexit.register(shutdown_rma_manager)

print("Flask app initialized")
print(f"Loaded {len(SCRAPER_FUNCTIONS)} scrapers: {list(SCRAPER_FUNCTIONS.keys())}")


@app.route('/')
@login_required
def index():
    """Serve the main HTML page - requires authentication"""
    return send_from_directory('static', 'index.html')


@app.route('/login')
def login():
    """Serve the login page"""
    # If already logged in, redirect appropriately
    user = get_current_user()
    if user:
        if user['is_admin']:
            return redirect(url_for('admin'))
        return redirect(url_for('index'))
    return send_from_directory('static', 'login.html')


@app.route('/admin')
@admin_required
def admin():
    """Serve the admin dashboard - requires admin privileges"""
    return send_from_directory('static', 'admin.html')


@app.route('/settings')
@login_required
def settings():
    """Serve the settings page - requires authentication"""
    return send_from_directory('static', 'settings.html')


@app.route('/admin/scrapers')
@admin_required
def admin_scrapers():
    """Serve the scraper management page - requires admin privileges"""
    return send_from_directory('static', 'admin_scrapers.html')


@app.route('/api/admin/scrapers', methods=['GET'])
@admin_required
def get_scrapers():
    """Get all scrapers with their status"""
    try:
        from database.models import DatabaseManager
        scrapers = DatabaseManager.get_all_scrapers()
        return jsonify({"success": True, "scrapers": scrapers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/toggle-scraper', methods=['POST'])
@admin_required
def toggle_scraper():
    """Toggle a scraper's enabled status"""
    try:
        from database.models import DatabaseManager
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        scraper_code = data.get('scraper_code')
        is_enabled = data.get('is_enabled')

        if not scraper_code or is_enabled is None:
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        success = DatabaseManager.toggle_scraper(scraper_code, is_enabled)

        if success:
            return jsonify({"success": True, "message": "Scraper updated successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to update scraper"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/scrapers/enabled', methods=['GET'])
@login_required
def get_enabled_scrapers():
    """Get list of enabled scraper codes"""
    try:
        from database.models import DatabaseManager
        enabled_scrapers = DatabaseManager.get_enabled_scrapers()
        return jsonify({"success": True, "scrapers": enabled_scrapers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/api-keys', methods=['GET'])
@admin_required
def get_api_keys():
    """Get all API keys (admin only)"""
    try:
        from database.models import DatabaseManager
        api_keys = DatabaseManager.get_all_api_keys()
        return jsonify({"success": True, "api_keys": api_keys})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/create-api-key', methods=['POST'])
@admin_required
def create_api_key():
    """Create a new API key (admin only)"""
    try:
        from database.models import DatabaseManager
        data = request.get_json() or {}
        description = data.get('description', 'API Key')

        # Get current user ID
        current_user = get_current_user()
        created_by = current_user['id'] if current_user else None

        api_key = DatabaseManager.create_api_key(description=description, created_by=created_by)

        if api_key:
            return jsonify({
                "success": True,
                "api_key": api_key,
                "message": "API key created successfully"
            })
        else:
            return jsonify({"success": False, "error": "Failed to create API key"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/toggle-api-key', methods=['POST'])
@admin_required
def toggle_api_key():
    """Enable or disable an API key (admin only)"""
    try:
        from database.models import DatabaseManager
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        api_key = data.get('api_key')
        is_active = data.get('is_active')

        if not api_key or is_active is None:
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        success = DatabaseManager.toggle_api_key(api_key, is_active)

        if success:
            return jsonify({"success": True, "message": "API key updated successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to update API key"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/delete-api-key', methods=['POST'])
@admin_required
def delete_api_key():
    """Delete an API key (admin only)"""
    try:
        from database.models import DatabaseManager
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        api_key = data.get('api_key')

        if not api_key:
            return jsonify({"success": False, "error": "API key is required"}), 400

        success = DatabaseManager.delete_api_key(api_key)

        if success:
            return jsonify({"success": True, "message": "API key deleted successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to delete API key"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    """Handle user login"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({
                "success": False,
                "error": "Email et mot de passe requis"
            }), 400

        # Verify credentials
        user = DatabaseManager.verify_user(email, password)

        if not user:
            return jsonify({
                "success": False,
                "error": "Email ou mot de passe incorrect"
            }), 401

        # Set session
        login_user(user)

        return jsonify({
            "success": True,
            "message": "Connexion réussie",
            "is_admin": user.get('is_admin', False),
            "name": user.get('name')
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Handle user logout"""
    logout_user()
    return jsonify({
        "success": True,
        "message": "Déconnexion réussie"
    })


@app.route('/logout')
def logout():
    """Logout and redirect to login page"""
    logout_user()
    return redirect(url_for('login'))


@app.route('/api/admin/create-user', methods=['POST'])
@admin_required
def api_create_user():
    """Create a new user - admin only"""
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        if not name or not email or not password:
            return jsonify({
                "success": False,
                "error": "Tous les champs sont requis"
            }), 400

        # Create user
        user_id = DatabaseManager.create_user(name, email, password, is_admin=False)

        if not user_id:
            return jsonify({
                "success": False,
                "error": "Un utilisateur avec cet email existe déjà"
            }), 400

        return jsonify({
            "success": True,
            "message": "Utilisateur créé avec succès",
            "user_id": user_id
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_get_users():
    """Get list of all users - admin only"""
    try:
        users = DatabaseManager.get_all_users(exclude_admin=True)

        return jsonify({
            "success": True,
            "users": users
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


@app.route('/api/admin/delete-user/<int:user_id>', methods=['DELETE'])
@admin_required
def api_delete_user(user_id):
    """Delete a user - admin only"""
    try:
        success = DatabaseManager.delete_user(user_id)

        if not success:
            return jsonify({
                "success": False,
                "error": "Impossible de supprimer cet utilisateur"
            }), 400

        return jsonify({
            "success": True,
            "message": "Utilisateur supprimé avec succès"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


@app.route('/api/compare', methods=['POST'])
@api_key_or_login_required
def compare():
    """
    Compare insurance quotes from all providers - requires authentication

    Expected JSON body (Complete Form Data):
    {
        "marque": "Renault",
        "modele": "Clio",
        "carburant": "diesel",
        "nombre_places": 5,
        "puissance_fiscale": 6,
        "date_mec": "2020-05-15",
        "type_plaque": "standard",
        "immatriculation": "WW378497",
        "valeur_neuf": 200000,
        "valeur_actuelle": 150000,
        "nom": "Alami",
        "prenom": "Ahmed",
        "telephone": "0661652022",
        "email": "ahmed@email.com",
        "date_naissance": "1990-01-15",
        "date_permis": "2010-03-20",
        "ville": "Casablanca",
        "assureur_actuel": "AXA",
        "consent": true
    }

    Also supports old/simple format:
    {
        "valeur_neuf": 65000,
        "valeur_venale": 45000
    }
    """
    try:
        # Get current user (or use special API user ID if API key auth)
        if hasattr(request, 'api_key_auth') and request.api_key_auth:
            user_id = -1  # Special ID for API key authenticated requests
            user_name = "API User"
            user_email = "api@external.com"
        else:
            current_user = get_current_user()
            user_id = current_user['id'] if current_user else None
            user_name = current_user.get('name', 'Unknown') if current_user else None
            user_email = current_user.get('email', 'unknown@email.com') if current_user else None

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        # Check if it's old format or new format
        is_old_format = 'valeur_neuf' in data and 'valeur_venale' in data
        is_new_format = 'marque' in data and 'carburant' in data

        if not is_old_format and not is_new_format:
            return jsonify({
                "success": False,
                "error": "Invalid request format. Required fields missing."
            }), 400

        # Handle old format (backward compatibility)
        if is_old_format and not is_new_format:
            valeur_neuf = data.get('valeur_neuf')
            valeur_venale = data.get('valeur_venale')

            if valeur_neuf is None or valeur_venale is None:
                return jsonify({
                    "success": False,
                    "error": "Both valeur_neuf and valeur_venale are required"
                }), 400

            try:
                valeur_neuf = float(valeur_neuf)
                valeur_venale = float(valeur_venale)
            except (TypeError, ValueError):
                return jsonify({
                    "success": False,
                    "error": "Values must be valid numbers"
                }), 400

            if valeur_neuf <= 0 or valeur_venale <= 0:
                return jsonify({
                    "success": False,
                    "error": "Values must be positive"
                }), 400

            if valeur_venale > valeur_neuf:
                return jsonify({
                    "success": False,
                    "error": "Current value cannot exceed new vehicle value"
                }), 400

            # Save minimal form submission for old format
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent')
            minimal_form_data = {
                'valeur_neuf': valeur_neuf,
                'valeur_actuelle': valeur_venale
            }
            form_submission_id = DatabaseManager.save_form_submission(
                user_id=user_id,
                form_data=minimal_form_data,
                ip_address=ip_address,
                user_agent=user_agent,
                user_name=user_name,
                user_email=user_email
            )

            # Get selected scrapers (if provided)
            selected_scrapers = data.get('selected_scrapers', None)

            # Fetch quotes with old format
            result = get_all_quotes({
                "valeur_neuf": valeur_neuf,
                "valeur_venale": valeur_venale
            }, user_id=user_id, form_submission_id=form_submission_id, selected_scrapers=selected_scrapers)

            return jsonify(result)

        # Handle new format (complete form data)
        # Validate required vehicle fields
        required_fields = ['marque', 'modele', 'carburant', 'nombre_places',
                          'puissance_fiscale', 'date_mec', 'type_plaque',
                          'immatriculation', 'valeur_neuf', 'valeur_actuelle']

        missing_fields = [f for f in required_fields if f not in data or data[f] == '']
        if missing_fields:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        # Validate numeric fields
        try:
            valeur_neuf = float(data.get('valeur_neuf'))
            valeur_actuelle = float(data.get('valeur_actuelle'))
            nombre_places = int(data.get('nombre_places'))
            puissance_fiscale = int(data.get('puissance_fiscale'))
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "error": "Invalid numeric values"
            }), 400

        if valeur_neuf <= 0 or valeur_actuelle <= 0:
            return jsonify({
                "success": False,
                "error": "Vehicle values must be positive"
            }), 400

        if valeur_actuelle > valeur_neuf:
            return jsonify({
                "success": False,
                "error": "Current value cannot exceed new vehicle value"
            }), 400

        # Save form submission to database
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        form_submission_id = DatabaseManager.save_form_submission(
            user_id=user_id,
            form_data=data,
            ip_address=ip_address,
            user_agent=user_agent,
            user_name=user_name,
            user_email=user_email
        )

        # Get selected scrapers (if provided)
        selected_scrapers = data.get('selected_scrapers', None)

        # Fetch quotes with new format (uses field mapper internally)
        result = get_all_quotes(data, user_id=user_id, form_submission_id=form_submission_id, selected_scrapers=selected_scrapers)

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/axa/update-quote', methods=['POST'])
@login_required
def update_axa_quote():
    """
    Update AXA quotation with selected options

    Expected JSON body:
    {
        "base_payload": {...},  // Original payload (contrat, vehicule, leadInfos)
        "quotation_id": 60273806,
        "id_lead": "00QbH00000RFPeTUAX",
        "pack_id": 3,  // 2=Basique, 3=Basique+, 4=Optimale, 5=Premium
        "user_selections": {  // Optional: user-selected option values by guarantee code
            "20": 2,  // Defense et Recours
            "500": 5  // P.F.C.P
        },
        "duration": "annual"  // "annual" or "semi"
    }
    """
    try:
        from scrapers.axa_scraper import update_axa_quotation, build_garanties_payload
        import copy

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        # Extract required fields
        base_payload = data.get('base_payload')
        quotation_id = data.get('quotation_id')
        id_lead = data.get('id_lead')
        pack_id = data.get('pack_id')
        user_selections = data.get('user_selections', {})
        duration = data.get('duration', 'annual')

        if not base_payload or not quotation_id or not pack_id:
            return jsonify({
                "success": False,
                "error": "base_payload, quotation_id, and pack_id are required"
            }), 400

        # Build the update payload
        update_payload = copy.deepcopy(base_payload)

        # Set modePaiement based on duration
        if duration == 'annual':
            update_payload["contrat"]["modePaiement"] = "12"
        else:
            update_payload["contrat"]["modePaiement"] = "06"

        # Add required fields for update request
        update_payload["idQuotation"] = quotation_id
        update_payload["idPack"] = pack_id
        update_payload["idLead"] = id_lead

        # Build garanties based on pack and user selections
        garanties = build_garanties_payload(pack_id, user_selections)
        update_payload["garanties"] = garanties

        # Make the API call
        result = update_axa_quotation(quotation_id, update_payload)

        if result:
            return jsonify({
                "success": True,
                "data": result,
                "pack_id": pack_id,
                "duration": duration
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to update AXA quotation"
            }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/mcma/update-quote', methods=['POST'])
@login_required
def update_mcma_quote():
    """
    Update MCMA quotation with selected options

    Expected JSON body:
    {
        "subscription_id": "...",
        "token": "...",
        "pack_name": "optimale" or "tout_risque",
        "broken_glass_value": 7000,  // 7000, 10000, or 15000
        "second_option_value": 20000  // For optimale: damageAndCollision (20000, 30000, 50000)
                                      // For tout_risque: franchise (3, 5, 10)
    }
    """
    try:
        from scrapers.mcma_scraper import update_mcma_quote as mcma_update

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        # Extract required fields
        subscription_id = data.get('subscription_id')
        token = data.get('token')
        pack_name = data.get('pack_name')
        broken_glass_value = data.get('broken_glass_value')
        second_option_value = data.get('second_option_value')

        if not subscription_id or not token or not pack_name:
            return jsonify({
                "success": False,
                "error": "subscription_id, token, and pack_name are required"
            }), 400

        if pack_name not in ['optimale', 'tout_risque']:
            return jsonify({
                "success": False,
                "error": "pack_name must be 'optimale' or 'tout_risque'"
            }), 400

        if not broken_glass_value or not second_option_value:
            return jsonify({
                "success": False,
                "error": "broken_glass_value and second_option_value are required"
            }), 400

        # Call the MCMA update function
        result = mcma_update(
            subscription_id=subscription_id,
            token=token,
            pack_name=pack_name,
            broken_glass_value=broken_glass_value,
            second_option_value=second_option_value
        )

        if result and result.get('success'):
            # Calculate taxes (16.5%)
            annual_price = result.get('annual_price', 0) or 0
            semi_annual_price = result.get('semi_annual_price', 0) or 0
            annual_taxes = round(annual_price * 0.165, 2)
            semi_annual_taxes = round(semi_annual_price * 0.165, 2)

            return jsonify({
                "success": True,
                "pack_name": pack_name,
                "broken_glass_value": broken_glass_value,
                "second_option_value": second_option_value,
                "annual": {
                    "prime_net": annual_price,
                    "taxes": annual_taxes,
                    "prime_total": round(annual_price + annual_taxes, 2)
                },
                "semi_annual": {
                    "prime_net": semi_annual_price,
                    "taxes": semi_annual_taxes,
                    "prime_total": round(semi_annual_price + semi_annual_taxes, 2)
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Failed to update MCMA quotation')
            }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500



def generate_pdf_bytes(all_plans, vehicle_info, client_info, duration='annual', branding=None, user_settings=None):
    """Internal function to generate PDF bytes"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch, mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from io import BytesIO
        from datetime import datetime
        from PIL import Image as PILImage

        def _fmt_pdf_num(v):
            """Format number for PDF: integer when whole, else 2 decimals (avoids 400000.0)."""
            if v is None: return 'N/A'
            try:
                n = float(v)
                return str(int(n)) if n == int(n) else f"{n:.2f}"
            except (TypeError, ValueError):
                return str(v) if v != '' else 'N/A'

        # Define coverage categories
        categories = {
            'Basique': {'patterns': ['basique', 'formule initiale', 'optimale mamda', 'basique oto']},
            'Intermédiaire': {'patterns': ['basique+', 'optimal oto', 'formule essentielle', 'confort']},
            'Collision': {'patterns': ['collision', 'confort oto', 'optimale axa']},
            'Premium': {'patterns': ['tous risques', 'formule premium', 'tous risques oto', 'premium', 'tout risque']}
        }

        # FIX: Sort providers consistently by provider_code (deterministic order)
        # Note: comparison_service returns 'code' not 'provider_code'
        print(f"[PDF DEBUG] ===== PDF Generation Started =====")
        print(f"[PDF DEBUG] Received {len(all_plans)} providers")
        for p in all_plans:
            code = p.get('code') or p.get('provider_code', '?')
            plan_count = len(p.get('plans', []))
            print(f"[PDF DEBUG]   Provider: {code} ({p.get('name', 'N/A')}) - {plan_count} plans")
        
        sorted_providers = sorted(all_plans, key=lambda p: p.get('code', p.get('provider_code', '')))
        
        # FIX: Assign provider letters consistently based on sorted order
        provider_code_to_letter = {}
        for idx, provider_data in enumerate(sorted_providers):
            # Handle both 'code' (from comparison_service) and 'provider_code' (legacy)
            provider_code = provider_data.get('code') or provider_data.get('provider_code', '')
            if provider_code and provider_code not in provider_code_to_letter:
                letter = chr(65 + len(provider_code_to_letter))  # A, B, C, D...
                provider_code_to_letter[provider_code] = letter
                print(f"[PDF DEBUG]   Assigned letter {letter} to provider {provider_code}")
        
        # FIX: Collect ALL plans from ALL providers first (with provider info)
        all_plans_with_provider = []
        for provider_data in sorted_providers:
            # Handle both 'code' (from comparison_service) and 'provider_code' (legacy)
            provider_code = provider_data.get('code') or provider_data.get('provider_code', '')
            anonymous_name = f"Assurance {provider_code_to_letter.get(provider_code, '?')}"
            
            for plan in provider_data.get('plans', []):
                plan_name = plan.get('plan_name', '').lower()
                plan_name_orig = plan.get('plan_name', 'N/A')
                pricing = plan.get('annual') if duration == 'annual' else plan.get('semi_annual')
                if not pricing:
                    print(f"[PDF DEBUG]   Skipping {plan_name_orig} ({provider_code}): No pricing data")
                    continue
                
                prime_total = pricing.get('prime_total', 0)
                if prime_total <= 0:
                    print(f"[PDF DEBUG]   Skipping {plan_name_orig} ({provider_code}): Invalid price {prime_total}")
                    continue
                
                print(f"[PDF DEBUG]   Collected: {plan_name_orig} ({provider_code}) - {prime_total:.2f} DH")
                all_plans_with_provider.append({
                    'provider_code': provider_code,
                    'provider_name': anonymous_name,
                    'plan': plan,
                    'plan_name': plan_name,
                    'plan_name_original': plan_name_orig,
                    'pricing': pricing,
                    'price': prime_total
                })
        
        # FIX: Categorize ALL plans, then pick cheapest per category
        categorized_offers = {}
        print(f"[PDF DEBUG] Processing {len(all_plans_with_provider)} plans for categorization")
        
        for plan_item in all_plans_with_provider:
            plan_name = plan_item['plan_name']
            prime_total = plan_item['price']
            provider_code = plan_item['provider_code']
            plan_name_orig = plan_item['plan_name_original']
            
            # Check which category this plan matches (check all categories)
            matched_category = None
            matched_pattern = None
            for cat_key, cat_info in categories.items():
                for pattern in cat_info['patterns']:
                    if pattern in plan_name:
                        matched_category = cat_key
                        matched_pattern = pattern
                        break
                if matched_category:
                    break  # First match wins (categories are mutually exclusive)
            
            if matched_category:
                current_best = categorized_offers.get(matched_category)
                current_price = current_best['price'] if current_best else float('inf')
                
                print(f"[PDF DEBUG] Plan: {plan_name_orig} ({provider_code}) | Price: {prime_total:.2f} | Category: {matched_category} | Pattern: {matched_pattern} | Current best: {current_price:.2f}")
                
                # Update if this is cheaper than current best in category
                if matched_category not in categorized_offers or prime_total < categorized_offers[matched_category]['price']:
                    if current_best:
                        print(f"[PDF DEBUG]   → REPLACING {current_best['plan_name']} ({current_best['provider']}) with {plan_name_orig} ({plan_item['provider_name']})")
                    categorized_offers[matched_category] = {
                        'provider': plan_item['provider_name'],
                        'plan_name': plan_name_orig,
                        'price': prime_total,
                        'pricing': plan_item['pricing'],
                        'plan': plan_item['plan']
                    }
            else:
                print(f"[PDF DEBUG] Plan: {plan_name_orig} ({provider_code}) | Price: {prime_total:.2f} | Category: NONE (no match)")
        
        print(f"[PDF DEBUG] Final categorized offers:")
        for cat, offer in categorized_offers.items():
            print(f"[PDF DEBUG]   {cat}: {offer['plan_name']} ({offer['provider']}) - {offer['price']:.2f} DH")
            if cat == 'Premium' and abs(offer['price'] - 8111.50) < 0.01:
                print(f"[PDF DEBUG]   ⚠️  WARNING: Premium price is 8111.50 - investigating source!")
                print(f"[PDF DEBUG]   ⚠️  Plan details: {offer['plan_name']} from {offer['provider']}")
                print(f"[PDF DEBUG]   ⚠️  Expected: Sanlam 'Formule premium' at 7091.43 DH")
        
        print(f"[PDF DEBUG] ===== PDF Generation Completed =====")

        if not categorized_offers:
            return None

        # Create PDF with tight margins (optimized for single page)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, 
                               topMargin=15*mm, bottomMargin=15*mm)

        elements = []
        styles = getSampleStyleSheet()

        # Compact styles (slightly reduced to keep everything on one page)
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=15,
            textColor=colors.HexColor('#1e40af'), spaceAfter=4*mm, alignment=TA_CENTER,
            fontName='Helvetica-Bold')

        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=7,
            textColor=colors.HexColor('#64748b'), spaceAfter=4*mm, alignment=TA_CENTER)

        section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=9,
            textColor=colors.HexColor('#1e40af'), spaceAfter=2*mm, spaceBefore=3*mm,
            fontName='Helvetica-Bold')

        offer_header_style = ParagraphStyle('OfferHeader', parent=styles['Heading3'], fontSize=8.5,
            textColor=colors.white, alignment=TA_LEFT, fontName='Helvetica-Bold', leading=10)

        offer_subheader_style = ParagraphStyle('OfferSubHeader', parent=styles['Normal'], fontSize=7.5,
            textColor=colors.HexColor('#0f172a'), alignment=TA_LEFT, fontName='Helvetica-Bold')

        offer_text_style = ParagraphStyle('OfferText', parent=styles['Normal'], fontSize=7,
            textColor=colors.HexColor('#111827'), alignment=TA_LEFT, leading=9)

        # Logo handling logic with branding support
        logo_path = None
        # Check branding first
        if branding and branding.get('logo_filename'):
            # Check static/logos first (project convention)
            param_filename = branding.get('logo_filename')
            possible_paths = [
                os.path.join(app.static_folder, 'logos', param_filename),
                os.path.join(app.static_folder, 'uploads', param_filename)
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    logo_path = p
                    break
        # Fallback to user settings
        elif user_settings and user_settings.get('logo_filename'):
            logo_path = os.path.join(app.static_folder, 'uploads', user_settings['logo_filename'])
            
        if logo_path and os.path.exists(logo_path):
            try:
                pil_img = PILImage.open(logo_path)
                img_width, img_height = pil_img.size
                aspect = img_height / float(img_width)
                # Make logo visually larger (approx twice previous maximum size)
                max_width, max_height = 80*mm, 30*mm
                
                if aspect > (max_height / max_width):
                    display_height = max_height
                    display_width = display_height / aspect
                else:
                    display_width = max_width
                    display_height = display_width * aspect
                logo = Image(logo_path, width=display_width, height=display_height)
                # Align logo to the right for a more premium layout
                logo.hAlign = 'RIGHT'
                elements.append(logo)
                elements.append(Spacer(1, 3*mm))
            except Exception as e:
                print(f"Logo error: {e}")

        # Title
        elements.append(Paragraph("Estimation Assurance Auto", title_style))
        elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", subtitle_style))

        # Client & Vehicle Info - Side by Side (show count similarly to "Meilleures Offres (4 catégories)")
        num_categories = len(categorized_offers)
        info_title = f"Informations ({num_categories} catégorie{'s' if num_categories > 1 else ''})"
        elements.append(Paragraph(info_title, section_style))
        
        info_data = [
            ['Client', '', 'Véhicule', ''],
            ['Nom', f"{client_info.get('nom', 'N/A')} {client_info.get('prenom', '')}", 
             'Marque', vehicle_info.get('marque', 'N/A')],
            ['Téléphone', client_info.get('telephone', 'N/A'), 
             'Modèle', vehicle_info.get('modele', 'N/A')],
            ['Email', client_info.get('email', 'N/A'), 
             'Puissance', f"{vehicle_info.get('puissance_fiscale', 'N/A')} CV"],
            ['Ville', client_info.get('ville', 'N/A'), 
             'Carburant', vehicle_info.get('carburant', 'N/A')],
            ['Date Naissance', client_info.get('date_naissance', 'N/A'), 
             'Places', vehicle_info.get('nombre_places', 'N/A')],
            ['Date Permis', client_info.get('date_permis', 'N/A'), 
             'Immatriculation', vehicle_info.get('immatriculation', 'N/A')],
            ['Assureur Actuel', client_info.get('assureur_actuel', 'Aucun'), 
             'Date MEC', vehicle_info.get('date_mec', 'N/A')],
            ['', '', 'Valeur Neuf', f"{_fmt_pdf_num(vehicle_info.get('valeur_neuf'))} DH"],
            ['', '', 'Valeur Actuelle', f"{_fmt_pdf_num(vehicle_info.get('valeur_actuelle'))} DH"],
            ['', '', 'Durée', '12 Mois' if duration == 'annual' else '6 Mois']
        ]

        info_table = Table(info_data, colWidths=[25*mm, 45*mm, 28*mm, 42*mm])
        info_table.setStyle(TableStyle([
            # First row like offers header: dark background, white text
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            # Body rows on white background
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 6.5),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd5e1')),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold')
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 4*mm))

        # Offers Section - 2x2 Grid
        elements.append(Paragraph(f"Meilleures Offres ({len(categorized_offers)} catégories)", section_style))
        
        sorted_offers = sorted(categorized_offers.items(), key=lambda x: x[1]['price'])
        
        # Create 2x2 grid of offers
        offer_tables = []
        for idx, (cat_key, offer) in enumerate(sorted_offers):
            pricing = offer['pricing']
            
            plan_obj = offer.get('plan', {})
            guarantees = plan_obj.get('guarantees', []) if isinstance(plan_obj, dict) else []
            selectable_fields = plan_obj.get('selectable_fields', []) if isinstance(plan_obj, dict) else []

            offer_rows = [
                [Paragraph(f"{idx+1}. {cat_key}", offer_header_style)],
                [Paragraph(offer['provider'], offer_subheader_style)],
                [Paragraph(offer['plan_name'], offer_text_style)],
                [Paragraph(f"Prime TTC: {offer['price']:.2f} DH", offer_subheader_style)],
                [Paragraph("Garanties:", offer_subheader_style)]
            ]

            # Add guarantees with thresholds/capital/franchise/selected option when available
            for g in guarantees:
                name = g.get('title') or g.get('guarantee_name') or g.get('name') or 'Garantie'
                included = 'Inclus' if g.get('is_included', True) else 'Non inclus'
                details = []
                if g.get('capital_guarantee') is not None:
                    try:
                        details.append(f"Plafond: {float(g.get('capital_guarantee')):,.2f} DH")
                    except Exception:
                        details.append(f"Plafond: {g.get('capital_guarantee')}")
                if g.get('franchise'):
                    details.append(f"Franchise: {g.get('franchise')}")
                if g.get('selected_option'):
                    details.append(f"Option: {g.get('selected_option')}")
                if g.get('prime_annual'):
                    try:
                        details.append(f"Prime: {float(g.get('prime_annual')):,.2f} DH")
                    except Exception:
                        details.append(f"Prime: {g.get('prime_annual')}")

                detail_str = (" — " + ", ".join(details)) if details else ""
                offer_rows.append([Paragraph(f"{name}: {included}{detail_str}", offer_text_style)])

            # Fallback to common pricing keys when guarantees list is empty
            if not guarantees:
                fallback_keys = [
                    ('RC', 'rc'), ('Défense', 'defense_recours'), ('Assistance', 'assistance'),
                    ('Ind. Cond.', 'individuelle_conducteur'), ('Bris Glace', 'bris_glace'),
                    ('Vol/Incendie', 'vol_incendie'), ('Dommages', 'dommages_collision')
                ]
                for label, key in fallback_keys:
                    val = pricing.get(key) if isinstance(pricing, dict) else None
                    display_val = f"{val} DH" if val is not None else 'N/A'
                    offer_rows.append([Paragraph(f"{label}: {display_val}", offer_text_style)])

            # Add selectable fields and defaults/selected options
            if selectable_fields:
                offer_rows.append([Paragraph("Options sélectionnables:", offer_subheader_style)])
                for f in selectable_fields:
                    title = f.get('title') or f.get('field_title') or f.get('field_name') or 'Option'
                    default = f.get('default') or f.get('selected_option') or ''
                    offer_rows.append([Paragraph(f"{title}: {default}", offer_text_style)])

            offer_table = Table(offer_rows, colWidths=[40*mm])
            offer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#0f172a')),
                ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
                ('BACKGROUND', (0, 3), (0, 3), colors.HexColor('#e6eefc')),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 1.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))

            offer_tables.append(offer_table)

        # Arrange offers in a single row (up to 4 offers side by side)
        max_cols = 4
        row_cells = []
        for table in offer_tables[:max_cols]:
            row_cells.append(table)
        while len(row_cells) < max_cols:
            row_cells.append('')

        grid_data = [row_cells]
        
        grid_table = Table(grid_data, colWidths=[40*mm] * max_cols, spaceBefore=2*mm, spaceAfter=2*mm)
        grid_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1*mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1*mm),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm)
        ]))

        elements.append(grid_table)
        elements.append(Spacer(1, 3*mm))

        # Disclaimer
        disclaimer_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=6.5,
            textColor=colors.HexColor('#6b7280'), alignment=TA_JUSTIFY, leading=9)
        
        num_insurances = len(provider_code_to_letter)
        disclaimer_text = """
        Note : Ces estimations sont fournies à titre indicatif sur la base de 3 assurances. Les prix et conditions peuvent varier selon votre profil.
        Tarif calculé sur la base d'un CRM 100 (Coefficient Réduction et Majoration).
        Vous serez contacté pour une cotation précise dans les plus brefs délais, afin de vous accompagner dans le choix de l'assurance la plus adaptée à vos besoins en fonction des informations complémentaires fournies.
        """
        elements.append(Paragraph(disclaimer_text.strip(), disclaimer_style))
        
        # Footer
        footer_text = "MesAssurances.ma - Comparateur d'Assurances au Maroc"
        if user_settings and user_settings.get('company_name'):
            footer_text = f"{user_settings['company_name']} - Courtier d'Assurances"
            
        # Override with branding footer if provided
        if branding and branding.get('footer_text'):
            footer_text = branding['footer_text']
            
        # Fixed footer drawing function
        def draw_footer(canvas, doc_obj):
            canvas.saveState()
            footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=6,
                textColor=colors.HexColor('#94a3b8'), alignment=TA_CENTER)
            
            p = Paragraph(footer_text, footer_style)
            w, h = p.wrap(doc_obj.width, doc_obj.bottomMargin)
            p.drawOn(canvas, doc_obj.leftMargin, doc_obj.bottomMargin - 10*mm)
            canvas.restoreState()

        # Build PDF
        doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None


def process_lead_background(lead_data, callback_url, branding=None):
    """Background task to scrape quotes, generate PDF, and send callback"""
    try:
        print(f"Processing background lead for {lead_data.get('email')}")
        
        # Normalize lead_data so scrapers get the same shape as Railway form (e.g. valeur_actuelle)
        # PythonAnywhere sends DB columns: prix_estime for current value; scrapers expect valeur_actuelle
        params_for_compare = dict(lead_data)
        if not params_for_compare.get('valeur_actuelle') and params_for_compare.get('prix_estime') is not None:
            params_for_compare['valeur_actuelle'] = params_for_compare['prix_estime']
        if not params_for_compare.get('valeur_actuelle') and params_for_compare.get('valeur_venale') is not None:
            params_for_compare['valeur_actuelle'] = params_for_compare['valeur_venale']
        
        # Call comparison service with normalized params (same as Railway form payload)
        # FIX: Always query all providers for PDF generation to ensure consistency
        # (Don't pass selected_scrapers=None explicitly - get_all_quotes defaults to all providers)
        comparison_result = get_all_quotes(params_for_compare, selected_scrapers=None)
        
        providers_with_plans = [p for p in comparison_result.get('providers', []) if p.get('plans')]
        
        if not providers_with_plans:
            print("No quotes found for this lead")
            return

        # Prepare info dicts
        # Note: map 'valeur_actuelle' from 'valeur_actuelle', 'valeur_venale', or 'prix_estime'
        valeur_actuelle = lead_data.get('valeur_actuelle')
        if not valeur_actuelle:
            valeur_actuelle = lead_data.get('valeur_venale')
        if not valeur_actuelle:
            valeur_actuelle = lead_data.get('prix_estime')

        vehicle_info = {
            'marque': lead_data.get('marque'),
            'modele': lead_data.get('modele'),
            'carburant': lead_data.get('carburant'),
            'puissance_fiscale': lead_data.get('puissance_fiscale'),
            'nombre_places': lead_data.get('nombre_places'),
            'immatriculation': lead_data.get('immatriculation'),
            'date_mec': lead_data.get('date_mec'),
            'valeur_neuf': lead_data.get('valeur_neuf'),
            'valeur_actuelle': valeur_actuelle,
        }
        
        client_info = {
            'nom': lead_data.get('nom'),
            'prenom': lead_data.get('prenom'),
            'telephone': lead_data.get('telephone'),
            'email': lead_data.get('email'),
            'ville': lead_data.get('ville'),
            'date_naissance': lead_data.get('date_naissance'),
            'date_permis': lead_data.get('date_permis'),
            'assureur_actuel': lead_data.get('assureur_actuel'),
        }

        # Generate PDF bytes
        pdf_bytes = generate_pdf_bytes(
            all_plans=comparison_result.get('providers', []),
            vehicle_info=vehicle_info,
            client_info=client_info,
            duration='annual',
            branding=branding
        )

        if not pdf_bytes:
            print("Failed to generate PDF")
            return

        # Send Callback
        print(f"Sending callback to {callback_url}")
        
        files = {
            'pdf': ('comparatif_assurance.pdf', pdf_bytes, 'application/pdf')
        }
        
        callback_data = {
            'email': lead_data.get('email'),
            'lead_id': lead_data.get('lead_id') or lead_data.get('id'),
            'success': 'true'
        }
        
        import requests
        resp = requests.post(callback_url, data=callback_data, files=files, timeout=45)
        print(f"Callback response: {resp.status_code}")

    except Exception as e:
        print(f"Background processing error: {e}")
        import traceback
        traceback.print_exc()


@app.route('/api/process-auto-lead', methods=['POST'])
def process_auto_lead():
    """Async endpoint to trigger auto insurance scraping and PDF generation."""
    import threading
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400
            
        lead_data = data.get('lead_data')
        callback_url = data.get('callback_url')
        branding = data.get('branding')
        
        if not lead_data or not callback_url:
             return jsonify({"success": False, "error": "lead_data and callback_url are required"}), 400
             
        # Start background thread
        thread = threading.Thread(
            target=process_lead_background,
            args=(lead_data, callback_url, branding)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "success": True,
            "message": "Processing started",
            "status": "accepted"
        }), 202
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/generate-comparison-pdf', methods=['POST'])
@login_required
def generate_comparison_pdf():
    """Generate professional one-page PDF comparison (sync)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        all_plans = data.get('all_plans', [])
        duration = data.get('duration', 'annual')
        vehicle_info = data.get('vehicle_info', {})
        client_info = data.get('client_info', {})
        branding = data.get('branding', None)

        if not all_plans:
            return jsonify({"success": False, "error": "No plans provided"}), 400

        # Get user settings
        from database.models import DatabaseManager
        user_id = session.get('user_id')
        user_settings = DatabaseManager.get_user_settings(user_id) if user_id else None

        # Generate PDF
        pdf_bytes = generate_pdf_bytes(all_plans, vehicle_info, client_info, duration, branding, user_settings)

        if not pdf_bytes:
             return jsonify({"success": False, "error": "PDF generation failed"}), 500

        # Create response
        from io import BytesIO
        response = send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"comparatif_assurance_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        )
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/generate-comparison-pdf_OLD', methods=['POST'])
@login_required
def generate_comparison_pdf_old():
    """Generate professional one-page PDF comparison"""
    try:
        from database.models import DatabaseManager
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch, mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from io import BytesIO
        from datetime import datetime
        from PIL import Image as PILImage

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        all_plans = data.get('all_plans', [])
        duration = data.get('duration', 'annual')
        vehicle_info = data.get('vehicle_info', {})
        client_info = data.get('client_info', {})

        if not all_plans:
            return jsonify({"success": False, "error": "No plans provided"}), 400

        # Define coverage categories
        categories = {
            'Basique': {'patterns': ['basique', 'formule initiale', 'optimale mamda', 'basique oto']},
            'Intermédiaire': {'patterns': ['basique+', 'optimal oto', 'formule essentielle', 'confort']},
            'Collision': {'patterns': ['collision', 'confort oto', 'optimale axa']},
            'Premium': {'patterns': ['tous risques', 'formule premium', 'tous risques oto', 'premium', 'tout risque']}
        }

        # FIX: Sort providers consistently by provider_code (deterministic order)
        # Note: comparison_service returns 'code' not 'provider_code'
        sorted_providers = sorted(all_plans, key=lambda p: p.get('code', p.get('provider_code', '')))
        
        # FIX: Assign provider letters consistently based on sorted order
        provider_code_to_letter = {}
        for idx, provider_data in enumerate(sorted_providers):
            # Handle both 'code' (from comparison_service) and 'provider_code' (legacy)
            provider_code = provider_data.get('code') or provider_data.get('provider_code', '')
            if provider_code and provider_code not in provider_code_to_letter:
                letter = chr(65 + len(provider_code_to_letter))  # A, B, C, D...
                provider_code_to_letter[provider_code] = letter
        
        # FIX: Collect ALL plans from ALL providers first (with provider info)
        all_plans_with_provider = []
        for provider_data in sorted_providers:
            # Handle both 'code' (from comparison_service) and 'provider_code' (legacy)
            provider_code = provider_data.get('code') or provider_data.get('provider_code', '')
            anonymous_name = f"Assurance {provider_code_to_letter.get(provider_code, '?')}"
            
            for plan in provider_data.get('plans', []):
                plan_name = plan.get('plan_name', '').lower()
                pricing = plan.get('annual') if duration == 'annual' else plan.get('semi_annual')
                if not pricing:
                    continue
                
                prime_total = pricing.get('prime_total', 0)
                if prime_total <= 0:
                    continue
                
                all_plans_with_provider.append({
                    'provider_code': provider_code,
                    'provider_name': anonymous_name,
                    'plan': plan,
                    'plan_name': plan_name,
                    'plan_name_original': plan.get('plan_name', 'N/A'),
                    'pricing': pricing,
                    'price': prime_total
                })
        
        # FIX: Categorize ALL plans, then pick cheapest per category
        categorized_offers = {}
        print(f"[PDF DEBUG] Processing {len(all_plans_with_provider)} plans for categorization")
        
        for plan_item in all_plans_with_provider:
            plan_name = plan_item['plan_name']
            prime_total = plan_item['price']
            provider_code = plan_item['provider_code']
            plan_name_orig = plan_item['plan_name_original']
            
            # Check which category this plan matches (check all categories)
            matched_category = None
            matched_pattern = None
            for cat_key, cat_info in categories.items():
                for pattern in cat_info['patterns']:
                    if pattern in plan_name:
                        matched_category = cat_key
                        matched_pattern = pattern
                        break
                if matched_category:
                    break  # First match wins (categories are mutually exclusive)
            
            if matched_category:
                current_best = categorized_offers.get(matched_category)
                current_price = current_best['price'] if current_best else float('inf')
                
                print(f"[PDF DEBUG] Plan: {plan_name_orig} ({provider_code}) | Price: {prime_total:.2f} | Category: {matched_category} | Pattern: {matched_pattern} | Current best: {current_price:.2f}")
                
                # Update if this is cheaper than current best in category
                if matched_category not in categorized_offers or prime_total < categorized_offers[matched_category]['price']:
                    if current_best:
                        print(f"[PDF DEBUG]   → REPLACING {current_best['plan_name']} ({current_best['provider']}) with {plan_name_orig} ({plan_item['provider_name']})")
                    categorized_offers[matched_category] = {
                        'provider': plan_item['provider_name'],
                        'plan_name': plan_name_orig,
                        'price': prime_total,
                        'pricing': plan_item['pricing'],
                        'plan': plan_item['plan']
                    }
            else:
                print(f"[PDF DEBUG] Plan: {plan_name_orig} ({provider_code}) | Price: {prime_total:.2f} | Category: NONE (no match)")
        
        print(f"[PDF DEBUG] Final categorized offers:")
        for cat, offer in categorized_offers.items():
            print(f"[PDF DEBUG]   {cat}: {offer['plan_name']} ({offer['provider']}) - {offer['price']:.2f} DH")
            if cat == 'Premium' and abs(offer['price'] - 8111.50) < 0.01:
                print(f"[PDF DEBUG]   ⚠️  WARNING: Premium price is 8111.50 - investigating source!")
                print(f"[PDF DEBUG]   ⚠️  Plan details: {offer['plan_name']} from {offer['provider']}")
                print(f"[PDF DEBUG]   ⚠️  Expected: Sanlam 'Formule premium' at 7091.43 DH")
        
        print(f"[PDF DEBUG] ===== PDF Generation Completed =====")

        if not categorized_offers:
            return jsonify({"success": False, "error": "No valid offers found"}), 400

        def _fmt_pdf_num(v):
            """Format number for PDF: integer when whole, else 2 decimals (avoids 400000.0)."""
            if v is None: return 'N/A'
            try:
                n = float(v)
                return str(int(n)) if n == int(n) else f"{n:.2f}"
            except (TypeError, ValueError):
                return str(v) if v != '' else 'N/A'

        # Get user settings for logo
        user_id = session.get('user_id')
        user_settings = DatabaseManager.get_user_settings(user_id) if user_id else None

        # Create PDF with tight margins (optimized for single page)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, 
                               topMargin=15*mm, bottomMargin=15*mm)

        elements = []
        styles = getSampleStyleSheet()

        # Compact styles (slightly reduced to keep everything on one page)
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=15,
            textColor=colors.HexColor('#1e40af'), spaceAfter=4*mm, alignment=TA_CENTER,
            fontName='Helvetica-Bold')

        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=7,
            textColor=colors.HexColor('#64748b'), spaceAfter=4*mm, alignment=TA_CENTER)

        section_style = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=9,
            textColor=colors.HexColor('#1e40af'), spaceAfter=2*mm, spaceBefore=3*mm,
            fontName='Helvetica-Bold')

        offer_header_style = ParagraphStyle('OfferHeader', parent=styles['Heading3'], fontSize=8.5,
            textColor=colors.white, alignment=TA_LEFT, fontName='Helvetica-Bold', leading=10)

        offer_subheader_style = ParagraphStyle('OfferSubHeader', parent=styles['Normal'], fontSize=7.5,
            textColor=colors.HexColor('#0f172a'), alignment=TA_LEFT, fontName='Helvetica-Bold')

        offer_text_style = ParagraphStyle('OfferText', parent=styles['Normal'], fontSize=7,
            textColor=colors.HexColor('#111827'), alignment=TA_LEFT, leading=9)

        # Logo
        if user_settings and user_settings.get('logo_filename'):
            logo_path = os.path.join('static', 'uploads', user_settings['logo_filename'])
            if os.path.exists(logo_path):
                try:
                    pil_img = PILImage.open(logo_path)
                    img_width, img_height = pil_img.size
                    aspect = img_height / float(img_width)
                    # Make logo visually larger (approx twice previous maximum size)
                    max_width, max_height = 80*mm, 30*mm
                    
                    if aspect > (max_height / max_width):
                        display_height = max_height
                        display_width = display_height / aspect
                    else:
                        display_width = max_width
                        display_height = display_width * aspect
                    logo = Image(logo_path, width=display_width, height=display_height)
                    # Align logo to the right for a more premium layout
                    logo.hAlign = 'RIGHT'
                    elements.append(logo)
                    elements.append(Spacer(1, 3*mm))
                except Exception as e:
                    print(f"Logo error: {e}")

        # Title
        elements.append(Paragraph("Estimation Assurance Auto", title_style))
        elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", subtitle_style))

        # Client & Vehicle Info - Side by Side (show count similarly to "Meilleures Offres (4 catégories)")
        num_categories = len(categorized_offers)
        info_title = f"Informations ({num_categories} catégorie{'s' if num_categories > 1 else ''})"
        elements.append(Paragraph(info_title, section_style))
        
        info_data = [
            ['Client', '', 'Véhicule', ''],
            ['Nom', f"{client_info.get('nom', 'N/A')} {client_info.get('prenom', '')}", 
             'Marque', vehicle_info.get('marque', 'N/A')],
            ['Téléphone', client_info.get('telephone', 'N/A'), 
             'Modèle', vehicle_info.get('modele', 'N/A')],
            ['Email', client_info.get('email', 'N/A'), 
             'Puissance', f"{vehicle_info.get('puissance_fiscale', 'N/A')} CV"],
            ['Ville', client_info.get('ville', 'N/A'), 
             'Carburant', vehicle_info.get('carburant', 'N/A')],
            ['Date Naissance', client_info.get('date_naissance', 'N/A'), 
             'Places', vehicle_info.get('nombre_places', 'N/A')],
            ['Date Permis', client_info.get('date_permis', 'N/A'), 
             'Immatriculation', vehicle_info.get('immatriculation', 'N/A')],
            ['Assureur Actuel', client_info.get('assureur_actuel', 'Aucun'), 
             'Date MEC', vehicle_info.get('date_mec', 'N/A')],
            ['', '', 'Valeur Neuf', f"{_fmt_pdf_num(vehicle_info.get('valeur_neuf'))} DH"],
            ['', '', 'Valeur Actuelle', f"{_fmt_pdf_num(vehicle_info.get('valeur_actuelle'))} DH"],
            ['', '', 'Durée', '12 Mois' if duration == 'annual' else '6 Mois']
        ]

        info_table = Table(info_data, colWidths=[25*mm, 45*mm, 28*mm, 42*mm])
        info_table.setStyle(TableStyle([
            # First row like offers header: dark background, white text
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            # Body rows on white background
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 6.5),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd5e1')),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold')
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 4*mm))

        # Offers Section - 2x2 Grid
        elements.append(Paragraph(f"Meilleures Offres ({len(categorized_offers)} catégories)", section_style))
        
        sorted_offers = sorted(categorized_offers.items(), key=lambda x: x[1]['price'])
        
        # Create 2x2 grid of offers
        offer_tables = []
        for idx, (cat_key, offer) in enumerate(sorted_offers):
            pricing = offer['pricing']
            
            plan_obj = offer.get('plan', {})
            guarantees = plan_obj.get('guarantees', []) if isinstance(plan_obj, dict) else []
            selectable_fields = plan_obj.get('selectable_fields', []) if isinstance(plan_obj, dict) else []

            offer_rows = [
                [Paragraph(f"{idx+1}. {cat_key}", offer_header_style)],
                [Paragraph(offer['provider'], offer_subheader_style)],
                [Paragraph(offer['plan_name'], offer_text_style)],
                [Paragraph(f"Prime TTC: {offer['price']:.2f} DH", offer_subheader_style)],
                [Paragraph("Garanties:", offer_subheader_style)]
            ]

            # Add guarantees with thresholds/capital/franchise/selected option when available
            for g in guarantees:
                name = g.get('title') or g.get('guarantee_name') or g.get('name') or 'Garantie'
                included = 'Inclus' if g.get('is_included', True) else 'Non inclus'
                details = []
                if g.get('capital_guarantee') is not None:
                    try:
                        details.append(f"Plafond: {float(g.get('capital_guarantee')):,.2f} DH")
                    except Exception:
                        details.append(f"Plafond: {g.get('capital_guarantee')}")
                if g.get('franchise'):
                    details.append(f"Franchise: {g.get('franchise')}")
                if g.get('selected_option'):
                    details.append(f"Option: {g.get('selected_option')}")
                if g.get('prime_annual'):
                    try:
                        details.append(f"Prime: {float(g.get('prime_annual')):,.2f} DH")
                    except Exception:
                        details.append(f"Prime: {g.get('prime_annual')}")

                detail_str = (" — " + ", ".join(details)) if details else ""
                offer_rows.append([Paragraph(f"{name}: {included}{detail_str}", offer_text_style)])

            # Fallback to common pricing keys when guarantees list is empty
            if not guarantees:
                fallback_keys = [
                    ('RC', 'rc'), ('Défense', 'defense_recours'), ('Assistance', 'assistance'),
                    ('Ind. Cond.', 'individuelle_conducteur'), ('Bris Glace', 'bris_glace'),
                    ('Vol/Incendie', 'vol_incendie'), ('Dommages', 'dommages_collision')
                ]
                for label, key in fallback_keys:
                    val = pricing.get(key) if isinstance(pricing, dict) else None
                    display_val = f"{val} DH" if val is not None else 'N/A'
                    offer_rows.append([Paragraph(f"{label}: {display_val}", offer_text_style)])

            # Add selectable fields and defaults/selected options
            if selectable_fields:
                offer_rows.append([Paragraph("Options sélectionnables:", offer_subheader_style)])
                for f in selectable_fields:
                    title = f.get('title') or f.get('field_title') or f.get('field_name') or 'Option'
                    default = f.get('default') or f.get('selected_option') or ''
                    offer_rows.append([Paragraph(f"{title}: {default}", offer_text_style)])

            offer_table = Table(offer_rows, colWidths=[40*mm])
            offer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#0f172a')),
                ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
                ('BACKGROUND', (0, 3), (0, 3), colors.HexColor('#e6eefc')),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 1.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))

            offer_tables.append(offer_table)

        # Arrange offers in a single row (up to 4 offers side by side)
        # This saves vertical space and gives a premium dashboard-like layout
        max_cols = 4
        row_cells = []
        for table in offer_tables[:max_cols]:
            row_cells.append(table)
        # Pad with empty cells if fewer than 4 offers
        while len(row_cells) < max_cols:
            row_cells.append('')

        grid_data = [row_cells]

        grid_table = Table(grid_data, colWidths=[40*mm] * max_cols, spaceBefore=2*mm, spaceAfter=2*mm)
        grid_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1*mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1*mm),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm)
        ]))

        elements.append(grid_table)
        elements.append(Spacer(1, 3*mm))

        # Disclaimer
        disclaimer_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=6.5,
            textColor=colors.HexColor('#6b7280'), alignment=TA_JUSTIFY, leading=9)
        
        num_insurances = len(provider_code_to_letter)
        disclaimer_text = (
            f"<b>Note :</b> Ces estimations sont fournies à titre indicatif sur la base de "
            f"{num_insurances} assurance{'s' if num_insurances > 1 else ''}. "
            "Les prix et conditions peuvent varier selon votre profil.<br/>"
            "Tarif calculé sur la base d'un CRM 100 (Coefficient Réduction et Majoration).<br/>"
            "Vous serez contacté pour une cotation précise dans les plus brefs délais, "
            "afin de vous accompagner dans le choix de l'assurance la plus adaptée à vos besoins en fonction des informations complémentaires fournies."
        )
        
        elements.append(Paragraph(disclaimer_text, disclaimer_style))

        # Capture footer text for fixed-position rendering
        footer_text = user_settings.get('footer_text') if (user_settings and user_settings.get('footer_text')) else None

        def draw_footer(canvas, doc_obj):
            """Draw a fixed footer at the bottom of the page with a small gap from the content."""
            if not footer_text:
                return
            canvas.saveState()
            footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=6,
                textColor=colors.HexColor('#9ca3af'), alignment=TA_CENTER, leading=8)
            footer_para = Paragraph(footer_text, footer_style)
            # Position footer slightly above the bottom margin to ensure visible gap after disclaimer
            width, height = A4
            footer_width = width - doc.leftMargin - doc.rightMargin
            footer_para.wrapOn(canvas, footer_width, 20*mm)
            footer_para.drawOn(canvas, doc.leftMargin, 12*mm)
            canvas.restoreState()

        # Build PDF with custom footer on each page (expected: single page)
        doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
        buffer.seek(0)

        # Generate filename
        num_offers = len(categorized_offers)
        filename = f'Estimation Assurance Auto - {num_offers} offre{"s" if num_offers > 1 else ""}.pdf'

        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

    except ImportError as e:
        return jsonify({
            "success": False,
            "error": f"PDF library not installed: {str(e)}. Please install reportlab: pip install reportlab"
        }), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    """Get user settings"""
    try:
        from database.models import DatabaseManager
        user_id = session.get('user_id')

        settings = DatabaseManager.get_user_settings(user_id)
        if not settings:
            settings = {
                'company_name': '',
                'logo_filename': '',
                'footer_text': ''
            }

        return jsonify({
            "success": True,
            "settings": settings
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    """Update user settings"""
    try:
        from database.models import DatabaseManager
        user_id = session.get('user_id')
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        company_name = data.get('company_name')
        footer_text = data.get('footer_text')

        # Get current settings to preserve logo if not updating
        current_settings = DatabaseManager.get_user_settings(user_id)
        logo_filename = current_settings.get('logo_filename') if current_settings else None

        success = DatabaseManager.save_user_settings(
            user_id=user_id,
            company_name=company_name,
            logo_filename=logo_filename,
            footer_text=footer_text
        )

        if success:
            return jsonify({"success": True, "message": "Settings updated successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to update settings"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/upload-logo', methods=['POST'])
@login_required
def upload_logo():
    """Upload user logo"""
    try:
        from database.models import DatabaseManager
        from werkzeug.utils import secure_filename

        user_id = session.get('user_id')

        if 'logo' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400

        file = request.files['logo']

        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

        if file_ext not in allowed_extensions:
            return jsonify({
                "success": False,
                "error": "Invalid file type. Allowed: PNG, JPG, JPEG, GIF, SVG"
            }), 400

        # Create uploads directory if not exists
        uploads_dir = os.path.join('static', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)

        # Generate unique filename
        filename = secure_filename(f"logo_{user_id}_{int(datetime.now().timestamp())}.{file_ext}")
        filepath = os.path.join(uploads_dir, filename)

        # Save file
        file.save(filepath)

        # Update database
        success = DatabaseManager.update_user_logo(user_id, filename)

        if success:
            return jsonify({
                "success": True,
                "filename": filename,
                "url": f"/static/uploads/{filename}"
            })
        else:
            # Clean up file if database update failed
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"success": False, "error": "Failed to update database"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/admin/export-database', methods=['GET'])
@admin_required
def export_database():
    """Export complete database to Excel - Admin only"""
    try:
        import tempfile
        from datetime import datetime
        from database.models import DatabaseManager

        # Create temporary file for Excel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_dir = tempfile.gettempdir()
        excel_file = os.path.join(temp_dir, f'insurance_database_{timestamp}.xlsx')

        # Export database to Excel
        success = DatabaseManager.export_database_to_excel(excel_file)

        if not success:
            return jsonify({
                "success": False,
                "error": "Failed to export database"
            }), 500

        # Send file to client
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f'insurance_database_{timestamp}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "providers": list(SCRAPER_FUNCTIONS.keys())
    })


@app.route('/api/providers', methods=['GET'])
def providers():
    """Get list of available providers"""
    from comparison_service import PROVIDER_INFO

    provider_list = []
    for code, info in PROVIDER_INFO.items():
        provider_list.append({
            "code": code,
            "name": info['name'],
            "color": info['color'],
            "logo": info['logo']
        })

    return jsonify({
        "success": True,
        "providers": provider_list
    })


if __name__ == '__main__':
    # Get PORT from environment (Railway sets this automatically)
    port = int(os.environ.get('PORT', 5000))

    # Get DEBUG mode from environment (set to False in production)
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'

    print(f"\n{'='*60}")
    print(f"🚀 Starting Insurance Comparison API")
    print(f"{'='*60}")
    print(f"   Host: 0.0.0.0")
    print(f"   Port: {port}")
    print(f"   Debug: {debug_mode}")
    print(f"   Scrapers: {', '.join(SCRAPER_FUNCTIONS.keys())}")
    print(f"{'='*60}\n")

    # Run Flask app
    # host='0.0.0.0' allows external connections (Railway requirement)
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=False  # Disable reloader for Railway compatibility
    )
