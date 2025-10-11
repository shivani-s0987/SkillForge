from google.auth.transport import requests
from google.oauth2 import id_token
from .models import CustomUser
from django.contrib.auth import authenticate
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from .api.user_serializers import CustomTokenObtainPairSerializer


class Google:
    """
    Handles validation of Google OAuth2 ID tokens.
    """

    @staticmethod
    def validate(access_token):
        """
        Validate the Google OAuth2 ID token.
        Args:
            access_token (str): Token received from Google Sign-In.
        Returns:
            dict | None: Decoded token info if valid, else None.
        """
        try:
            # Verify token with Google and your backend's client ID
            id_info = id_token.verify_oauth2_token(
                access_token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

            # Ensure token issuer is Google
            if id_info.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                print("❌ Invalid issuer:", id_info.get("iss"))
                return None

            # Optionally, print user info for debugging
            print("✅ Google token verified successfully:")
            print("  - Email:", id_info.get("email"))
            print("  - Name:", id_info.get("name"))
            print("  - Picture:", id_info.get("picture"))

            return id_info

        except ValueError as e:
            print("❌ Google token verification failed (ValueError):", str(e))
            return None
        except Exception as e:
            print("❌ Google token verification failed (General):", type(e).__name__, str(e))
            return None


def login_social_user(email, password, role):
    """
    Authenticate a user with email & password and return JWT tokens.

    Args:
        email (str): User's email.
        password (str): User's password (from settings.SOCIAL_AUTH_PASSWORD).
        role (str): Role (e.g., 'student', 'tutor', etc.).

    Returns:
        dict: User info + JWT tokens.
    """
    user = authenticate(email=email, password=password)
    if not user:
        raise AuthenticationFailed('Invalid credentials.')

    token_serializer = CustomTokenObtainPairSerializer(
        data={'email': email, 'password': password, 'role': role}
    )

    if token_serializer.is_valid():
        token_data = token_serializer.validated_data
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'access_token': token_data['access_token'],
            'refresh_token': token_data['refresh_token']
        }
    else:
        raise AuthenticationFailed('Token generation failed.')


def register_social_user(provider, email, username, first_name, last_name, role):
    """
    Register or login a social user using Google OAuth2.

    Args:
        provider (str): Social provider (e.g., 'google').
        email (str): User's email from Google.
        username (str): Display name from Google.
        first_name (str): First name from Google.
        last_name (str): Last name from Google.
        role (str): Role in the system.

    Returns:
        dict: User info + JWT tokens.
    """
    try:
        user = CustomUser.objects.get(email=email)

        # If user exists and provider matches, log in
        if provider == user.auth_provider:
            return login_social_user(email, settings.SOCIAL_AUTH_PASSWORD, role)
        else:
            raise AuthenticationFailed(
                detail=f'Please continue your login using {user.auth_provider}.'
            )

    except CustomUser.DoesNotExist:
        # Register a new user if not found
        new_user = CustomUser(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            auth_provider=provider,
            is_verified=True,
            role=role
        )
        new_user.set_password(settings.SOCIAL_AUTH_PASSWORD)
        new_user.save()

        return login_social_user(
            email=new_user.email,
            password=settings.SOCIAL_AUTH_PASSWORD,
            role=role
        )
