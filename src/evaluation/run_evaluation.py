import json
import requests
import random
import os

DATASET_PATH = os.path.expanduser("data/News_Category_Dataset_v3.json")
API_URL = "http://news-classifier-api:8080/evaluate"
SAMPLE_SIZE = 250

def load_and_sample_dataset(file_path, sample_size):
    articles = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                articles.append({
                    "text": data.get("headline", ""),
                    "true_label": data.get("category", "").upper()
                })
            except json.JSONDecodeError as e:
                print(f"Avertissement: Ignoré une ligne JSON malformée: {e}")
                continue
    
    if len(articles) > sample_size:
        return random.sample(articles, sample_size)
    return articles

if __name__ == "__main__":
    print(f"Chargement et échantillonnage du dataset depuis : {DATASET_PATH}...")
    evaluation_data = load_and_sample_dataset(DATASET_PATH, SAMPLE_SIZE)

    if not evaluation_data:
        print("Aucune donnée n'a pu être chargée pour l'évaluation. Vérifiez le chemin du dataset et son contenu.")
    else:
        print(f"Envoi de {len(evaluation_data)} articles à l'API pour évaluation ({API_URL})...")
        try:
            response = requests.post(API_URL, json=evaluation_data, timeout=300)
            response.raise_for_status()
            result = response.json()
            print("Évaluation réussie !")
            print(f"Accuracy: {result.get('accuracy', 'N/A'):.4f}")
            print(f"Nombre d'éléments évalués: {result.get('evaluated_items', 'N/A')}")
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de l'envoi de la requête d'évaluation: {e}")
        except json.JSONDecodeError:
            print(f"Erreur lors du décodage de la réponse JSON de l'API: {response.text}")
        except Exception as e:
            print(f"Une erreur inattendue est survenue: {e}")
