import requests
import discord
from discord.ext import commands
from discord.ext import tasks
import mysql.connector
from bs4 import BeautifulSoup

class file():
    def __init__(self):
        self.LineData = []

    def read_from_file(self):    
        file = open("creds.txt", "r")
        lines = file.readlines()
        for l in lines:
            self.LineData.append(l.strip('\n'))
        if self.LineData[3] == "no_pwd":
            self.LineData[3] = ""
        file.close()
        return (self.LineData[0], self.LineData[1], self.LineData[2], self.LineData[3], self.LineData[4], self.LineData[5])
    
    async def set_channel_id(self, new_id):
        prev_channel = int(self.read_from_file()[-1])
        if not new_id.isdigit():
            emb = discord.Embed(title = "An error occured while trying to change channels", description = f"Δεν υπάρχει κανάλι με αναγνωριστικό {new_id}", color = 0xad0919)
            await client.get_channel(prev_channel).send(embed = emb)
            return None
        
        if int(new_id) == prev_channel:
            emb = discord.Embed(title = "An error occured while trying to change channels", description = f"Το κανάλι ειδοποιήσεων έχει ήδη id {new_id}", color = 0xad0919)
            await client.get_channel(prev_channel).send(embed = emb)
            return None

        file = open("creds.txt", "r")
        lines = file.readlines()
        file.close()

        file = open("creds.txt", "a")
        self.LineData[-1] = str(new_id)
        lines[-1] = str(new_id)
        file.truncate(0)

        for ele in lines:
            file.write(ele)
            
        file.close()

        setid = discord.Embed(title = "Update Channel ID Changed", description = f"Το κανάλι ειδοποιήσεων άλλαξε στο κανάλι με αναγνωριστικό {lines[-1]}", color = 0xf5426f)
        await client.get_channel(prev_channel).send(embed = setid)

class dbConnection():
    def __init__(self):
        fileObj = file()
        args = fileObj.read_from_file()
        self.database_conn = None
        self.host = args[1]
        self.user = args[2]
        self.database_name = args[4]
        self.pwd = args[3]
        self.conn = self.connect()
        self.cursor = self.conn.cursor()

    def connect(self):
        try:
            self.database_conn = mysql.connector.connect(
                host = self.host,
                user = self.user,
                password = "",
                database = self.database_name
            )
            return self.database_conn
        except:
            pass
        
    def cursor_getter(self):
        return self.cursor

    def database_conn_getter(self):
        return self.database_conn

    def database_name_getter(self):
        return self.database_name

class Scrap():
    def __init__(self):
        fileObj = file()
        self.dbObj = dbConnection()
        self.cur = self.dbObj.cursor_getter()
        arg_tuple = fileObj.read_from_file()
        self.channel_id = int(arg_tuple[5])
        self.db = self.dbObj.database_conn_getter()
        self.db_name = self.dbObj.database_name_getter()

    # Returns 2 Lists (Name, Price) that have the names and prices of the products (data retrieved from the DB)
    def db_getter(self):
        product_names = []
        product_prices = []
        interface = self.cur
        interface.execute(f"USE {self.db_name}")
        interface.execute("SELECT URL,NAME,PRICE FROM products")
        result_set = interface.fetchall()
        
        for row in result_set:
            product_names.append(row[1])
            product_prices.append(row[2])

        return product_names, product_prices

    # Function that adds the link param to the db
    async def addInfoToDb(self, link):
        page = requests.get(link, headers = {"User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36'})
        soup = BeautifulSoup(page.content, 'html.parser')

        name_append = soup.select_one('.page-title').get_text()
        price_append = soup.find("strong", {"class": "dominant-price"}).get_text()
        interface = self.cur
        interface.execute(f"SELECT * FROM products WHERE NAME = '{name_append}' ")
        channel = client.get_channel(self.channel_id)

        if interface.fetchall() == []:
            if '/s/' in link:
                c = i = 0
                while i < len(link) and c <= 2:
                    if link[i] == ".":
                        c += 1
                    if c <= 2:
                        i += 1
                        
                val = (f"{link[:i+5]}",f"{name_append}",f"{price_append[0:len(price_append)-2]}")
                interface.execute("INSERT INTO products (URL, NAME, PRICE) VALUES (%s,%s,%s)", val)
                addembed = discord.Embed(title = "Item Added To List", description = "Το αντικείμενο προστέθηκε στην ΒΔ", color = 0x63f549)
                await channel.send(embed = addembed)
                self.db.commit()
                return True
        return False

    # Function that deletes an arg from the db
    async def delInfoFromDb(self, argument):
        try:
            interface = self.cur
            if 'http' in argument:
                if '/s/' in argument:
                    c = 0
                    i = 0
                    while i < len(argument) and c <= 2:
                        if argument[i] == ".":
                            c += 1
                        if c <= 2:
                            i += 1
                argument = argument[:i+5]
                SQL = f"DELETE FROM products WHERE URL = '{argument}'"
                interface.execute("SELECT COUNT(URL) FROM products")
            else:
                SQL = f"DELETE FROM products WHERE NAME = '{argument}'"
                interface.execute("SELECT COUNT(NAME) FROM products")
                
            r = interface.fetchone()
            interface.execute(SQL)  
            interface.execute(f"SELECT COUNT(URL) FROM products")
            r_new = interface.fetchone()
            channel = client.get_channel(self.channel_id)
            
            if r != r_new:
                remembed = discord.Embed(title = "Item Removed", description = "Το αντικείμενο διαγράφτηκε από την ΒΔ", color = 0x63f549)
            else:
                remembed = discord.Embed(title = "Item Not Found", description = "Το αντικείμενο δεν βρέθηκε στην ΒΔ", color = 0xad0919)
            
            self.db.commit()
            await channel.send(embed = remembed)
        except Exception as e:
            print(e)

    # Function to handle the scenario in which the user tried to add an item that already exists.
    async def alreadyExists(self):
        channel = client.get_channel(self.channel_id)
        throw_embed = discord.Embed(title = "Error Adding Item To List", description = "The item you tried adding to the list already exists.", color = 0xad0919)
        await channel.send(embed = throw_embed)

    # Function that handles the search command
    async def searchInfoFromDb(self,argument):
        interface = self.cur
        if '/s/' in argument:
            c = i = 0
            while i < len(argument) and c <= 2:
                if argument[i] == ".":
                    c += 1
                if c <= 2:
                    i += 1
        argument = argument[:i+5]
        interface.execute(f"SELECT * FROM products WHERE URL = '{argument}'")
        channel = client.get_channel(self.channel_id)
        if len(interface.fetchall()) != 0:
            embed = discord.Embed(title="Table Search", description = "Το αντικείμενο βρίσκεται στην ΒΔ", color = 0x63f549)
        else:
            embed = discord.Embed(title="Table Search", description = "Το αντικείμενο δεν μπορούσε να βρεθεί στην ΒΔ", color = 0xad0919)
        await channel.send(embed = embed)

    # Function that handles mode changing (>mode {argument} command)
    async def changeMode(self, argument):
        interface = self.cur
        interface.execute(f"SELECT Mode FROM settings")
        
        SQL_CHECK = interface.fetchone()[0]
        channel = client.get_channel(self.channel_id)

        # Validation Check in Event Oriented Programming
        if argument.upper() == "UPDATE" or argument.upper() == "ALWAYS":
            # Check for the state of the "Mode" Record in the DB.
            if argument.upper() != SQL_CHECK:
                if argument == "update":
                    SQL = "UPDATE settings SET Mode = 'UPDATE'"
                    interface.execute(SQL)
                elif argument == "always":
                    SQL = "UPDATE settings SET Mode = 'ALWAYS'"
                    interface.execute(SQL)
                change_embed = discord.Embed(title = f"Mode Successfully Set To {argument.upper()}", description = f"Η μέθοδος αποστολής ειδοποιήσεων άλλαξε επιτυχώς στην μέθοδο: {argument.upper()}", color = 0x63f549)
            else:
                change_embed = discord.Embed(title = f"Mode Already Set To {SQL_CHECK}", description = "Προσπαθήσατε να αλλάξετε το mode στην ήδη υπαρκτή τιμή του.", color = 0xad0919)
        else:
            change_embed = discord.Embed(title = "Mode Does Not Exist", description = "Προσπαθήσατε να αλλάξετε το mode σε μια τιμή που δεν υπάρχει ή που δεν υποστηρίζεται!", color = 0xad0919)

        # Sends the Embed 
        await channel.send(embed = change_embed)
        self.db.commit()

    # Function that changes the percentage threshold at which the message will be sent by the bot, if the bot is set on "Update" mode.
    async def changePercentage(self, percent):
        interface = self.cur
        interface.execute("SELECT PERCENTAGE FROM settings")
        old_percent = interface.fetchone()[0]

        interface.execute(f"UPDATE settings SET PERCENTAGE = '{percent}'")
        self.db.commit()

        changePercentageEmbed = discord.Embed(title = "Update Percentage Update", description = "Ανανεώθηκε το απαραίτητο ποσοστό διαφοράς τιμής ώστε να σταλθεί ειδοποίηση", color=0xf5426f)
        changePercentageEmbed.add_field(name = "Νεό ποσοστό:", value = percent + "%", inline = True)
        changePercentageEmbed.add_field(name = "Προηγούμενο ποσοστό:", value = old_percent + "%", inline = True)

        channel = client.get_channel(self.channel_id)
        await channel.send(embed = changePercentageEmbed)
    
    # Repeatedly scrapes the skroutz website
    @tasks.loop(minutes = 2)
    async def scrap(self):
        channel = client.get_channel(self.channel_id)
        name,price = self.db_getter()
        interface = self.cur

        interface.execute("SELECT Mode FROM settings")
        result = interface.fetchone()[0].lower()

        if result == "always":
            for x in range(len(name)):
                embed = discord.Embed(title = "Skroutz Update", description = "Ανανέωση τιμών skroutz για τα τελευταία 15 λεπτά στα αγαπημένα σου αντικείμενα", color = 0xf5426f)
                embed.add_field(name = "Αντικείμενο:", value = str(name[x]), inline = False)
                embed.add_field(name = "Νέα Τιμή:", value = str(price[x])+'€', inline = True)
                embed.add_field(name = "Προηγούμενη Τιμή:", value = str(price[x]+'€'), inline = True)
                await channel.send(embed = embed)
        elif result == "update":
            for x in range(len(name)):
                interface.execute(f"SELECT URL FROM products WHERE NAME = '{name[x]}'")

                page = requests.get(interface.fetchone()[0], headers = {"User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36'})
                soup = BeautifulSoup(page.content, 'html.parser')

                timh_skroutz = soup.find("div", {"class": "price"}).get_text()
                timh_skroutz = timh_skroutz[0:len(timh_skroutz)-2]

                r = timh_skroutz.split(",")
                pr = price[x].split(",")
                
                euros = r[0]
                cents = r[1]
                
                euros_p = pr[0]
                cents_p = pr[1]
                
                final_skroutz = float(euros) + float(cents) / 100
                final_database = float(euros_p) + float(cents_p) / 100

                interface.execute("SELECT PERCENTAGE FROM settings")
                perc_db = interface.fetchone()[0]

                v = abs((final_skroutz - final_database) / abs(final_database) * 100)
                
                if final_skroutz - final_database != 0:
                    if v >= float(perc_db):
                        percentage = round((final_skroutz - final_database) / final_database * 100, 2)
                        embed = discord.Embed(title = "Skroutz Update", description = "Ανανέωση τιμών skroutz για τα τελευταία 15 λεπτά στα αγαπημένα σου αντικείμενα", color = 0xf5426f)
                        embed.add_field(name = "Αντικείμενο:", value = str(name[x]), inline = False)
                        embed.add_field(name = "Προηγούμενη Τιμή:", value = str(price[x]) + '€', inline = True)
                        embed.add_field(name = "Νέα Τιμή:", value = str(final_skroutz) + '€', inline = True)
                        if final_skroutz - final_database > 0:
                            embed.add_field(name = "Άνοδος Τιμής:", value = str(percentage) + '%', inline = False)
                        else:
                            embed.add_field(name = "Κάθοδος Τιμής:", value = str(abs(percentage)) + '%', inline = False)
                        await channel.send(embed = embed)
                interface.execute(f"UPDATE products SET PRICE = '{timh_skroutz}' WHERE NAME = '{name[x]}'")
                
        self.db.commit()



client = commands.Bot(command_prefix=">")
fileObj = file()
scrapObj = Scrap()
args = fileObj.read_from_file()

@client.command()
async def percentage(ctx, arg):
    await scrapObj.changePercentage(arg)

@client.command()
async def add(ctx, arg):
    state = await scrapObj.addInfoToDb(arg)
    if not state:
        await scrapObj.alreadyExists()

@client.command()
async def remove(ctx, arg):
    await scrapObj.delInfoFromDb(arg)

@client.command()
async def search(ctx, arg):
    await scrapObj.searchInfoFromDb(arg)

@client.command()
async def mode(ctx, arg):
    await scrapObj.changeMode(arg)

@client.command()
async def setid(ctx, arg):
    await fileObj.set_channel_id(arg)
    
@client.event
async def on_ready():
    scrapObj.scrap.start()

client.run(args[0])
