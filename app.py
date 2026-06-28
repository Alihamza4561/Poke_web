from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
import os
from dotenv import load_load_env # 🆕 Import the loader environment utility

# Load the keys out of the hidden local .env file
load_dotenv()

app = Flask(__name__)

# ==========================================================================
# 🎛️ SECURED DATABASE CONFIGURATION
# ==========================================================================
app.config['SECRET_KEY'] = 'super-secret-key-change-this-later'

# 🔐 Reads the URL string dynamically, falling back to local database if missing
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


login_manager = LoginManager()
login_manager.login_view = 'login' 
login_manager.init_app(app)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    # Establishes a virtual relationship link to the monster table
    monsters = db.relationship('CachedPokemon', backref='creator', lazy=True)

class CachedPokemon(db.Model):
    __tablename__ = 'cached_pokemon'
    
    id = db.Column(db.Integer, primary_key=True) 
    name = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(500))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    types_json = db.Column(db.Text)
    stats_json = db.Column(db.Text)
    evolution_json = db.Column(db.Text)
    abilities_json = db.Column(db.Text)
    is_custom = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def parse_evolution_chain(chain_data):
    chain = []
    current = chain_data
    while current:
        poke_name = current['species']['name']
        details = current['evolution_details']
        method_info = "Initial Form"
        if details:
            det = details[0]
            if det.get('trigger', {}).get('name') == 'level-up' and det.get('min_level'):
                method_info = f"Level {det['min_level']}"
            elif det.get('trigger', {}).get('name') == 'use-item' and det.get('item'):
                item_name = det['item']['name'].replace("-", " ").title()
                method_info = f"Use {item_name}"
            elif det.get('trigger', {}).get('name') == 'trade':
                method_info = "Trade"
            else:
                method_info = "Special Condition"
        
        img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{current['species']['url'].split('/')[-2]}.png"
        chain.append({"name": poke_name.title(), "image": img_url, "method": method_info})
        current = current['evolves_to'][0] if current.get('evolves_to') else None
    return chain

@app.route('/')
def home():
    regions = [
        {
            "name": "kanto", "display": "Kanto", "gen": "Gen 1", 
            "map_url": "https://www.pokemon.com/static-assets/content-assets/cms2/img/misc/_tiles/pokemon-center/2023/03272023/inline/kanto.png",
            "offset": 0, "limit": 151
        },
        {
            "name": "johto", "display": "Johto", "gen": "Gen 2", 
            "map_url": "https://tse3.mm.bing.net/th/id/OIP.6DbXmep4BoYDpgzUSkvL8AHaE-?cb=thfvnextfalcon3&rs=1&pid=ImgDetMain&o=7&rm=3",
            "offset": 151, "limit": 100
        },
        {
            "name": "hoenn", "display": "Hoenn", "gen": "Gen 3", 
            "map_url": "https://wallpaperaccess.com/full/4441507.jpg",
            "offset": 251, "limit": 135
        },
        {
            "name": "sinnoh", "display": "Sinnoh", "gen": "Gen 4", 
            "map_url": "https://tse3.mm.bing.net/th/id/OIP.IDLLX1e4kiksjnfXwjHskwHaKe?cb=thfvnextfalcon3&w=1448&h=2048&rs=1&pid=ImgDetMain&o=7&rm=3",
            "offset": 386, "limit": 107
        },
        {
            "name": "unova", "display": "Unova", "gen": "Gen 5", 
            "map_url": "https://tse1.mm.bing.net/th/id/OIP.Nz1_JDI1pgAzXL-ooiZxOQHaHa?cb=thfvnextfalcon3&rs=1&pid=ImgDetMain&o=7&rm=3",
            "offset": 493, "limit": 156
        },
        {
            "name": "kalos", "display": "Kalos", "gen": "Gen 6", 
            "map_url": "https://thfvnext.bing.com/th/id/R.060b7ac82521820af23cddb7e697f0c9?rik=4FjYLVHaedQ%2biQ&riu=http%3a%2f%2fimg2.wikia.nocookie.net%2f__cb20140917104423%2fes.pokemon%2fimages%2f7%2f7e%2fMapa_de_Kalos_XY_se%c3%b1alizado.png&ehk=ZNiIuhrgwlucn%2fwUgm0rXnzVK%2fPdnUlZ%2fRTRvoducOk%3d&risl=&pid=ImgRaw&r=0",
            "offset": 649, "limit": 72
        },
        {
            "name": "alola", "display": "Alola", "gen": "Gen 7", 
            "map_url": "https://thfvnext.bing.com/th/id/R.18d9a0b8ab7f91bcb4a6558b1cec47a8?rik=VSAO4PDNdWl3TQ&riu=http%3a%2f%2fpokecompany.com%2fwp-content%2fuploads%2f2016%2f05%2fLocalizaciones_Alola.jpg&ehk=NGrTIKKfV4sm0E8c%2b9ftH12Pgk%2fGi9qAtw62rJ16f38%3d&risl=&pid=ImgRaw&r=0",
            "offset": 721, "limit": 88
        },
        {
            "name": "galar", "display": "Galar", "gen": "Gen 8", 
            "map_url": "https://tse2.mm.bing.net/th/id/OIP.LVD3Jxbu-X18fKSxSs_ekQHaKe?cb=thfvnextfalcon3&rs=1&pid=ImgDetMain&o=7&rm=3",
            "offset": 809, "limit": 89
        },
        {
            "name": "paldea", "display": "Paldea", "gen": "Gen 9", 
            "map_url": "https://progameguides.com/wp-content/uploads/2022/09/Pokemon-Scarlet-and-Violet-Paldea-Map-1024x576.jpg",
            "offset": 898, "limit": 127
        }
    ]
    return render_template('home.html', regions=regions)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        # Check if username is already taken in MySQL
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists! Try a different one.')
            return redirect(url_for('register'))
            
        # 🔥 ENCRYPT PASSWORD before storing it in MySQL
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
       
        if user and check_password_hash(user.password_hash, password):
            login_user(user) 
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password. Try again!')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out safely.')
    return redirect(url_for('home'))

@app.route('/create', methods=['GET', 'POST'])
@login_required 
def create_monster():
    if request.method == 'POST':
        name = request.form.get('monster_name').strip().title()
        primary_type = request.form.get('primary_type')
        custom_img_url = request.form.get('monster_image').strip()
        ability_name = request.form.get('ability_name').strip().title()
        ability_desc = request.form.get('ability_desc').strip()
        hp = int(request.form.get('hp', 70))
        attack = int(request.form.get('attack', 70))
        
        if not custom_img_url:
            custom_img_url = "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=300"
        
        last_custom = CachedPokemon.query.filter(CachedPokemon.id >= 10000).order_by(CachedPokemon.id.desc()).first()
        new_id = last_custom.id + 1 if last_custom else 10000
        
        custom_monster = CachedPokemon(
            id=new_id, name=name, image=custom_img_url, height=1.8, weight=60.0,
            types_json=json.dumps([primary_type]),
            stats_json=json.dumps([{"name": "HP", "value": hp}, {"name": "ATTACK", "value": attack}]),
            evolution_json=json.dumps([{"name": name, "image": custom_img_url, "method": "Synthesized Form"}]),
            abilities_json=json.dumps([{"name": ability_name, "description": ability_desc}]),
            is_custom=True,
            user_id=current_user.id 
        )
        db.session.add(custom_monster)
        db.session.commit()
        return redirect(url_for('custom_vault'))
        
    return render_template('create.html')

@app.route('/custom-vault')
@login_required 
def custom_vault():
   
    custom_monsters = CachedPokemon.query.filter_by(is_custom=True, user_id=current_user.id).all()
    return render_template('custom_vault.html', custom_monsters=custom_monsters)

@app.route('/region/<region_name>', methods=['GET', 'POST'])
def region_view(region_name):
    if request.method == 'POST':
        search_query = request.form.get('pokemon_name', '').strip().lower()
        if search_query:
            return redirect(url_for('pokemon_detail', pokemon_name=search_query))

    region_limits = {
        "kanto": {"offset": 0, "limit": 151}, 
        "johto": {"offset": 151, "limit": 100},
        "hoenn": {"offset": 251, "limit": 135}, 
        "sinnoh": {"offset": 386, "limit": 107},
        "unova": {"offset": 493, "limit": 156},
        "kalos": {"offset": 649, "limit": 72},
        "alola": {"offset": 721, "limit": 88},
        "galar": {"offset": 809, "limit": 89},
        "paldea": {"offset": 898, "limit": 127}
    }
    
    config = region_limits.get(region_name.lower(), {"offset": 0, "limit": 151})
    url = f"https://pokeapi.co/api/v2/pokemon?offset={config['offset']}&limit={config['limit']}"
    res = requests.get(url)
    pokemon_list = []
    
    if res.status_code == 200:
        raw_results = res.json()['results']
        for item in raw_results:
            exact_poke_id = int(item['url'].split('/')[-2])
            
            pokemon_list.append({
                "id": exact_poke_id,
                "name": item['name'].title().replace("-", " "),
                "image": f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{exact_poke_id}.png"
            })
            
    return render_template('region.html', pokemon_list=pokemon_list, region_name=region_name.title())

@app.route('/pokemon/<pokemon_name>')
def pokemon_detail(pokemon_name):
    is_id = pokemon_name.isdigit()
    if is_id:
        local_match = CachedPokemon.query.filter_by(id=int(pokemon_name)).first()
    else:
        local_match = CachedPokemon.query.filter_by(name=pokemon_name.title()).first()
        
    if local_match:
        pokemon_info = {
            "id": local_match.id, "name": local_match.name, "image": local_match.image, "height": local_match.height, "weight": local_match.weight,
            "types": json.loads(local_match.types_json), "stats": json.loads(local_match.stats_json), "evolution_chain": json.loads(local_match.evolution_json), "abilities": json.loads(local_match.abilities_json)
        }
        return render_template('detail.html', pokemon=pokemon_info)

    url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}"
    res = requests.get(url)
    if res.status_code != 200:
        return f"<h1>Error: Pokémon '{pokemon_name}' not found!</h1><a href='/'>Go Home</a>", 404
        
    data = res.json()
    species_res = requests.get(data["species"]["url"]).json()
    evolution_path = parse_evolution_chain(requests.get(species_res["evolution_chain"]["url"]).json()['chain'])
    
    detailed_abilities = []
    for a in data["abilities"]:
        ability_title = a["ability"]["name"].title().replace("-", " ")
        ability_res = requests.get(a["ability"]["url"])
        effect_text = "No description available."
        if ability_res.status_code == 200:
            for entry in ability_res.json().get("effect_entries", []):
                if entry["language"]["name"] == "en":
                    effect_text = entry["short_effect"]
                    break
        detailed_abilities.append({"name": ability_title, "description": effect_text})
    
    types = [t["type"]["name"].title() for t in data["types"]]
    stats = [{"name": s["stat"]["name"].upper(), "value": s["base_stat"]} for s in data["stats"]]
    
    new_cache_entry = CachedPokemon(
        id=data["id"], name=data["name"].title(), image=data["sprites"]["other"]["official-artwork"]["front_default"],
        height=data["height"] / 10, weight=data["weight"] / 10, types_json=json.dumps(types), stats_json=json.dumps(stats),
        evolution_json=json.dumps(evolution_path), abilities_json=json.dumps(detailed_abilities), is_custom=False
    )
    db.session.add(new_cache_entry)
    db.session.commit()

    pokemon_info = {
        "id": data["id"], "name": data["name"].title(), "image": new_cache_entry.image, "height": data["height"] / 10, "weight": data["weight"] / 10, "types": types, "stats": stats, "evolution_chain": evolution_path, "abilities": detailed_abilities
    }
    return render_template('detail.html', pokemon=pokemon_info)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)