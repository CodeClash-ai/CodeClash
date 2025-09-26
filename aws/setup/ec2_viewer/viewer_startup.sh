export GITHUB_TOKEN=''

sudo apt update
sudo apt install -y python3-pip python3.12-venv
sudo apt install nginx apache2-utils -y
sudo snap install aws-cli --classic
sudo apt install certbot python3-certbot-nginx -y

git clone https://klieret:${GITHUB_TOKEN}@github.com/emagedoc/CodeClash.git
cd CodeClash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

aws configure

mkdir logs

sudo htpasswd -c /etc/nginx/.htpasswd admin

sudo tee /etc/nginx/sites-available/default > /dev/null << 'EOF'
server {
    listen 80;
    server_name emagedoc.xyz;

    location / {
        auth_basic "Restricted Access";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

sudo systemctl start nginx
sudo systemctl enable nginx

sudo certbot --nginx -d emagedoc.xyz
