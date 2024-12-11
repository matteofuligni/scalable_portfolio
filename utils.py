import pandas as pd
import numpy as np
import requests
import os
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

def load_transaction_data(path):
    """
    Load transaction data fron the csv dawnloaded from scalabel
    """
    data = pd.read_csv(path, sep=";", thousands='.', decimal=',').drop(columns='reference')
    data = data[data['status'] == 'Executed']
    return data

def load_isin_ticker_data(path):
    """
    Load ISIN-Ticker table fron the csv dawnloaded from from the Xetra Exchange 
    """
    data = pd.read_csv(path, sep=";", usecols=['ISIN', 'Mnemonic'])
    return data

def get_unique_isin(df):
    """
    Return the unique ISINs list
    """
    unique_isin = df['isin'].dropna().unique()
    return unique_isin

def get_ticker_From_isin(df, isin):
    return

def isin_to_description(df):
    """
    Crea un dizionario che associa gli 'isin' unici alle rispettive 'description'.

    Parameters:
    df (pd.DataFrame): DataFrame contenente le colonne 'isin' e 'description'.

    Returns:
    dict: Dizionario con gli 'isin' come chiavi e le rispettive 'description' come valori.
    """

    filtered_df = df[['isin', 'description']].dropna(subset=['isin', 'description'])
    unique_isin = filtered_df.drop_duplicates(subset='isin')

    isin_dict = dict(zip(unique_isin['isin'], unique_isin['description']))

    return isin_dict

class TwoWayDict:
    def __init__(self):
        self.forward = {}
        self.reverse = {}

    def add(self, ticker, isin):
        # Evita duplicati o valori vuoti
        if ticker and isin:
            self.forward[ticker] = isin
            self.reverse[isin] = ticker

    def populate_dict(self, df, isins):
        for isin in isins:
            # Trova il ticker corrispondente
            result = df.loc[df['ISIN'] == isin, 'Mnemonic']
            if not result.empty:
                ticker = result.iloc[0]  # Recupera il primo valore trovato
                self.add(ticker, isin)
            else:
                print(f"ISIN {isin} non trovato nel DataFrame.")

    def get(self, key):
        # Cerca nei dizionari forward e reverse
        return self.forward.get(key) or self.reverse.get(key)



def get_positions(df):
    df = df.dropna(subset=['isin'])
    df.loc[:, 'type'] = df['type'].replace('Savings plan', 'Buy')    
    isins = get_unique_isin(df)
    isin_dict = isin_to_description(df)
    positions = pd.DataFrame(columns=['ISIN', 'Description', 'Total Shares', 'Avg Price', 'Status'])
    
    for isin in isins:
        subDataFrame = df[df['isin'] == isin]
        total_shares = 0
        total_buy_shares = 0
        total_buy_amount = 0
        total_sell_shares = 0
        total_sell_amount = 0
        for _, row in subDataFrame.iterrows():
            if row['type'] == 'Buy':
                total_buy_shares += row['shares']
                total_buy_amount += row['amount']
            elif row['type'] == 'Sell':
                total_sell_shares += row['shares']
                total_sell_amount += row['amount']
            else:
                raise('There is a problem in the "type" column')
            
        avg_buy_price = -total_buy_amount/total_buy_shares
        avg_sell_price = total_sell_amount/total_sell_shares if total_sell_shares !=0 else 0
        total_shares = total_buy_shares - total_sell_shares
        profit, status = [abs(total_buy_amount + total_sell_amount), 'Sold'] if total_shares <= 0.1 else [0, 'Hodl']     
        
        description = isin_dict.get(isin, "ISIN non trovato")
        newLine = {'ISIN':isin, 'Description':description, 'Total Shares':total_shares, 'Avg Buy Price':avg_buy_price,
                   'Avg Sell Price':avg_sell_price, 'Status':status, 'Profit':profit}
        positions = pd.concat([positions, pd.DataFrame([newLine])], ignore_index=True)
        
    #positions = positions[abs(positions['Total Shares']) >= 0.001]

    return positions
    
def format_table(df):
    # Formatta i numeri con separatori per migliaia e due cifre decimali
    formatted_df = df.copy()
    formatted_df['Total Shares'] = formatted_df['Total Shares'].apply(lambda x: f"{x:,.3f}")
    formatted_df['Avg Price'] = formatted_df['Avg Price'].apply(lambda x: f"{x:,.3f}")
    return formatted_df

def compute_total_portfolio(df):
    """_summary_

    Args:
        df (_type_): _description_

    Returns:
        _type_: _description_
    """
    total_position = (df['Total Shares']*df['Avg Price']).sum()
    return total_position 

def get_data_from_yahoo(ticker, check, interval='1d', period='1y'):
    """
    Check if the data is already present in the csv file, if not download the data from yahoo fiance and save it in the csv file.
    If present, download only the missing data from the last date presenti in the csv file.

    Args:
        isin (str): _description_
        interval (str): _description_
        period (str): _description_
    
    Returns:
        dataFrame: _description_
    """
    if check:
        path = os.path.join('data', 'historic_data', ticker, interval)
        existing_data = load_data_from_csv(path)
        today_date = datetime.today().strftime('%Y-%m-%d')
        last_date = pd.to_datetime(existing_data['Date']).max()
        if today_date > last_date:
            delta = datetime.today() - last_date
            delta = delta.days
            if delta//30 > 0 and delta//365 == 0:
                period = '1y'
            elif delta//365 > 0 and delta//365*10 == 0:
                period = '10y'
            elif delta//365*10 > 0:
                period = '20y'
            else:
                period = '30y'
            new_data = yf.download(ticker, interval=interval, period=period)
        new_data = new_data[new_data.index > last_date]
        if not new_data.empty:
            df = pd.concat([existing_data, new_data])
        else:
            df = existing_data
    else:
        return yf.download(ticker, interval=interval, period=period)


def save_data_to_csv(df, path):
    """
    Aggiungere il controllo dei dati presenti e fino a che data.
    Se si stanno scaricando dati giornalieri, controllare se i dati sono già presenti e scaricare solo i dati mancanti più recenti a partire dall'ultimo giorno presente.
    Stessa cosa per i dati mensili e annuali.
    
    Args:
        df (pd.DataFrame): DataFrame contenente i dati storici.
        interval (str): Intervallo di tempo dei dati (es. '1d', '1mo', '1y').
        path (str): Percorso del file CSV dove salvare i dati.
    """
    if os.path.exists(path):
        today_date = datetime.today().strftime('%Y-%m-%d')
        existing_data = pd.read_csv(path, sep=';', decimal=',')
        last_date = pd.to_datetime(existing_data['Date']).max()
        if today_date > last_date:
            new_data = df[df.index > last_date]
            
            
        else:
            raise ValueError("The DataFrame does not contain a 'Date' column.")
        if not new_data.empty:
            df = pd.concat([existing_data, new_data])
        else:
            print(f"Nessun nuovo dato da aggiungere per {path}")
    else:
        print(f"Nessun dato esistente trovato per {path}. Creazione di un nuovo file.")
    
    
    df.to_csv(path, sep=';', decimal=',', index=False)


def check_if_path_exists(path):
    """_summary_
    check if path exists, if not create it
    
    Args: path (str): directory path
    """
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        print(f'Path {path} created')
    else:
        print(f'Path {path} already exists')
    
def load_data_from_csv(path):
    """_summary_
    
    Args:
        path (_type_): _description_
    
    Returns:
        _type_: _description_
    """
    return pd.read_csv(path, sep=';', decimal=',')
    
    
def download_data(tickers, interval, period):
    """_summary_
    
    Args:
        tickers (str): _description_
        interval (str): _description_
        period (str): _description_
    
    Returns:
        _type_: _description_
    """
    def process_ticker(ticker):
        path = os.path.join('data', 'historic_data', ticker, interval)
        check_if_path_exists(path)
        check_if_data_exists(ticker, interval, period)
        data = get_data_from_yahoo(ticker, interval, period)
        save_data_to_csv(data, path)

    with ThreadPoolExecutor() as executor:
        executor.map(process_ticker, tickers)
    
    return 

def check_if_data_exists(ticker, interval, period):
    """_summary_
    
    Args:
        tickers (str): _description_
        interval (str): _description_
    
    Returns:
        bool: _description_
    """

    path = os.path.join('data', 'historic_data', ticker, interval, f"{ticker}.csv")
    if not os.path.exists(path):
        return False
    return True