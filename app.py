from flask import Flask, render_template, redirect, url_for, request, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required, UserMixin
from models import db, User, Post, Reply
from forms import LoginForm, RegisterForm, PostForm, ReplyForm, ProfileForm
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'devsecret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

@app.template_filter('user_from_id')
def user_from_id(user_id):
    user = User.query.get(user_id)
    return user.username if user else 'Unknown'

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class UserLogin(UserMixin):
    def __init__(self, user):
        self.user = user
        self.id = user.id
    def is_admin(self):
        return self.user.role == 'admin'
    def is_bot(self):
        return self.user.role == 'bot'

@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user:
        return UserLogin(user)
    return None

def setup_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('admin')
            db.session.add(admin)
        if not User.query.filter_by(username='antiphish').first():
            bot = User(username='antiphish', role='bot')
            bot.set_password('!!!') # Not used
            db.session.add(bot)
        db.session.commit()

# Ensure database setup runs on every start (both dev and prod)
setup_db()

@app.route('/')
def index():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(UserLogin(user))
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already taken')
        else:
            user = User(username=form.username.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful. Please log in.')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, body=form.body.data, author_id=current_user.user.id)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('post.html', form=form, new=True)

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def show_post(post_id):
    post = Post.query.get_or_404(post_id)
    author = User.query.get(post.author_id)
    form = ReplyForm()
    if form.validate_on_submit() and current_user.is_authenticated:
        reply = Reply(body=form.body.data, author_id=current_user.user.id, post_id=post_id)
        db.session.add(reply)
        db.session.commit()
        # AI bot check
        if '@antiphish run check' in form.body.data:
            url = form.body.data.split('@antiphish run check', 1)[1].strip()
            # Simulate AI check (replace with API call to Replit AI)
            ai_reply = Reply(
                body=f"[AntiPhish Bot] Safety report for {url}:\nThis is a placeholder response.",
                author_id=User.query.filter_by(username='antiphish').first().id,
                post_id=post_id
            )
            db.session.add(ai_reply)
            db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    replies = Reply.query.filter_by(post_id=post_id).order_by(Reply.created_at).all()
    return render_template('post.html', post=post, author=author, replies=replies, form=form, new=False)

@app.route('/users')
def users():
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/user/<username>', methods=['GET', 'POST'])
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    form = ProfileForm(obj=user)
    if user.id == current_user.user.id and form.validate_on_submit():
        user.bio = form.bio.data
        db.session.commit()
        flash('Profile updated.')
        return redirect(url_for('profile', username=username))
    return render_template('profile.html', user=user, form=form)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    form = ProfileForm(obj=current_user.user)
    if form.validate_on_submit():
        current_user.user.bio = form.bio.data
        db.session.commit()
        flash('Settings updated.')
        return redirect(url_for('settings'))
    return render_template('settings.html', form=form)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin():
        abort(403)
    users = User.query.all()
    posts = Post.query.all()
    return render_template('admin.html', users=users, posts=posts)

if __name__ == '__main__':
    app.run(debug=True)
