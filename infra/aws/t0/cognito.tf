resource "aws_cognito_user_pool" "t0" {
  name                     = "fincilia-t0"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "ON"
  user_pool_tier           = "ESSENTIALS"
  deletion_protection      = "ACTIVE"

  software_token_mfa_configuration {
    enabled = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 3
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "fincilia-t0-web"
  user_pool_id = aws_cognito_user_pool.t0.id

  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = ["http://localhost:53000/api/auth/callback/cognito"]
  logout_urls                          = ["http://localhost:53000/entrar"]
  enable_token_revocation              = true
  prevent_user_existence_errors        = "ENABLED"

  access_token_validity  = 15
  id_token_validity      = 15
  refresh_token_validity = 1

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

# Cliente separado para la superficie publica. Mantenerlo independiente del
# cliente localhost evita ampliar el conjunto de callbacks de cualquiera de los
# dos entornos. Habilitar Google aqui prepara la federacion, pero no activa OIDC
# en el runtime ni adjudica DRG-00.
resource "aws_cognito_user_pool_client" "google_web" {
  name         = "fincilia-google-web"
  user_pool_id = aws_cognito_user_pool.t0.id

  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["Google"]
  callback_urls                        = ["https://fincilia.com/api/auth/callback/cognito"]
  logout_urls                          = ["https://fincilia.com/entrar"]
  enable_token_revocation              = true
  prevent_user_existence_errors        = "ENABLED"

  access_token_validity  = 15
  id_token_validity      = 15
  refresh_token_validity = 1

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_cognito_user_pool_domain" "t0" {
  domain       = "fincilia-t0-${local.account_suffix}"
  user_pool_id = aws_cognito_user_pool.t0.id
}
