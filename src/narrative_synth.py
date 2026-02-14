import os
import random
import argparse
from faker import Faker
from datetime import datetime, timedelta

# Initialize Faker
fake = Faker()

class DataGenerator:
    """Methods to generate structured data points for narratives."""
    
    @staticmethod
    def generate_amount():
        return round(random.uniform(100.0, 50000.0), 2)

    @staticmethod
    def generate_transaction_id():
        return fake.uuid4()

    @staticmethod
    def generate_account_id():
        return fake.iban()

    @staticmethod
    def generate_name():
        return fake.name()

    @staticmethod
    def generate_ip():
        return fake.ipv4()

    @staticmethod
    def generate_date(start_date='-1y'):
        return fake.date_time_between(start_date=start_date).strftime("%Y-%m-%d %H:%M:%S")

class NarrativeRenderer:
    """Templates to convert structured data into unstructured text."""
    
    TEMPLATES = [
        "Analyst Note: Suspicious activity detected on account {account_id}. A transfer of ${amount} was initiated by {name} (IP: {ip}) on {date}. The transaction {transaction_id} was flagged due to velocity rules.",
        "Incident Report: Fraud alert generated for transaction {transaction_id}. User {name} attempted a wire transfer of ${amount} to an external beneficiary. The IP address {ip} is geolocated to a high-risk jurisdiction. Action taken: Account {account_id} frozen pending investigation.",
        "Case Summary: Subject {name} is under review for potential money laundering. Transaction history shows a series of structured deposits totaling ${amount} on {date}. Source funds trace back to account {account_id}. Associated IP: {ip}.",
        "Internal Memo: Please review the recent activity for client {name}. An unusual withdrawal of ${amount} occurred on {date} (Ref: {transaction_id}). The login originated from {ip}, which is consistent with known botnet signatures.",
        "Fraud Operations Log: {date} - System flagged transaction {transaction_id} involving account {account_id}. Amount: ${amount}. Customer {name} claims they did not authorize this access. IP Log: {ip}."
    ]

    @staticmethod
    def render(data):
        template = random.choice(NarrativeRenderer.TEMPLATES)
        return template.format(**data)

class SiloManager:
    """Manages the creation and population of organization silos."""
    
    def __init__(self, base_dir="data/synthetic"):
        self.base_dir = base_dir

    def create_silo(self, org_name):
        path = os.path.join(self.base_dir, org_name)
        os.makedirs(path, exist_ok=True)
        return path

    def save_narrative(self, org_name, filename, content):
        path = os.path.join(self.base_dir, org_name, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

def generate_scenario_data(count):
    data_points = []
    for _ in range(count):
        data = {
            'amount': DataGenerator.generate_amount(),
            'transaction_id': DataGenerator.generate_transaction_id(),
            'account_id': DataGenerator.generate_account_id(),
            'name': DataGenerator.generate_name(),
            'ip': DataGenerator.generate_ip(),
            'date': DataGenerator.generate_date()
        }
        data_points.append(data)
    return data_points

def main():
    parser = argparse.ArgumentParser(description="Priva-Fed Synthetic Narrative Generator")
    parser.add_argument('--orgs', type=int, default=3, help='Number of organizations to simulate')
    parser.add_argument('--count', type=int, default=100, help='Number of documents per organization')
    parser.add_argument('--config', type=str, default='finance', help='Scenario configuration')
    
    args = parser.parse_args()
    
    print(f"Initializing Narrative-Synth for scenario: {args.config}")
    print(f"Generating data for {args.orgs} organizations, {args.count} documents each.")

    silo_manager = SiloManager()

    for i in range(1, args.orgs + 1):
        org_name = f"org_{chr(64 + i)}"  # org_A, org_B, org_C...
        silo_path = silo_manager.create_silo(org_name)
        print(f"Created silo: {silo_path}")
        
        data_points = generate_scenario_data(args.count)
        
        for idx, point in enumerate(data_points):
            narrative = NarrativeRenderer.render(point)
            filename = f"report_{idx:04d}.txt"
            silo_manager.save_narrative(org_name, filename, narrative)
        
        print(f"Populated {org_name} with {args.count} narratives.")

    print("\nGeneration Complete.")

if __name__ == "__main__":
    main()
