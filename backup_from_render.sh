#!/bin/bash
# Manual script to backup database from Render before deploying

echo "🔄 Backing up database from Render..."
echo ""
echo "Instructions:"
echo "1. Go to your Render dashboard"
echo "2. Open the Shell for your web service"
echo "3. Run: cat ratings.db | base64"
echo "4. Copy the output"
echo "5. Paste it into a file called 'db_backup.txt'"
echo ""
echo "Then run: base64 -d db_backup.txt > ratings.db"
echo "Then run: git add ratings.db && git commit -m 'Update database before deploy' && git push"
echo ""
read -p "Press Enter when done..."
