from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL, Length
from flask_ckeditor import CKEditorField


##WTForm
# The length caps match the column sizes in main.py. SQLite ignores them but Postgres rejects
# longer values, so without the caps an over-long field would be a 500 instead of a form error.
class CreatePostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired(), Length(max=250)])
    subtitle = StringField("Subtitle", validators=[DataRequired(), Length(max=250)])
    img_url = StringField("Blog Image URL", validators=[DataRequired(), URL(), Length(max=250)])
    body = CKEditorField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Length(max=100)])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    submit = SubmitField("Sign Me Up!")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Let Me In!")


class CommentForm(FlaskForm):
    # The length cap keeps comment sanitizing fast; deeply nested HTML gets slow to clean.
    comment_text = CKEditorField("Comment", validators=[DataRequired(), Length(max=10000)])
    submit = SubmitField("Submit Comment")
