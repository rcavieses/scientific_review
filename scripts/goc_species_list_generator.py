#!/usr/bin/env python3
"""
Generate GOC (Gulf of California) Species List

Creates a CSV file with scientifically validated species found in the
Gulf of California, organized by ecological group and habitat.

This serves as input for FishBase parameter queries.
"""

import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Comprehensive GOC species organized by ecological group
GOC_SPECIES_DATABASE = {
    # Demersal/Bottom dwellers - Rocky areas
    'Rocky_Bottom': {
        'Scorpaena guttata': 'California scorpionfish',
        'Scorpaena mystes': 'Baileyi scorpionfish',
        'Sebastes caurinus': 'Copper rockfish',
        'Sebastes flavidus': 'Yellowtail rockfish',
        'Sebastes maliger': 'Quillback rockfish',
        'Sebastes melanops': 'Black rockfish',
        'Ophiodon elongatus': 'Lingcod',
        'Hyperlophus exilis': 'Dwarf surfperch',
        'Chirps pictichthys': 'Spotted crevice kelpfish',
    },

    # Demersal/Bottom - Sandy/Soft bottom
    'Sandy_Bottom': {
        'Paralichthys californicus': 'California halibut',
        'Platichthys stellatus': 'Starry flounder',
        'Hippoglossina stomata': 'Bigmouth sole',
        'Paralabrax clathratus': 'Barred sand bass',
        'Paralabrax auroguttatus': 'Gulf grouper',
        'Citharichthys stigmaeus': 'Speckled sanddab',
        'Argyropelecus aculeatus': 'Hatchetfish',
    },

    # Pelagic/Midwater - Small pelagics
    'Small_Pelagics': {
        'Sardinops sagax': 'Pacific sardine',
        'Engraulis mordax': 'Northern anchovy',
        'Opisthonema libertate': 'Pacific thread herring',
        'Harengula thrissina': 'False herring',
        'Hyperlophus exilis': 'Dwarf surfperch',
    },

    # Pelagic/Midwater - Medium pelagics
    'Medium_Pelagics': {
        'Trachurus symmetricus': 'Jack mackerel',
        'Scomber japonicus': 'Pacific mackerel',
        'Auxis thazard': 'Frigate mackerel',
        'Euthynnus lineatus': 'Black skipjack',
        'Seriola lalandi': 'Yellowtail amberjack',
        'Caranx ignobilis': 'Giant trevally',
        'Caranx melampygus': 'Bluefin trevally',
    },

    # Pelagic/Midwater - Tunas and large pelagics
    'Large_Pelagics': {
        'Thunnus obesus': 'Bigeye tuna',
        'Thunnus albacares': 'Yellowfin tuna',
        'Thunnus alalunga': 'Albacore tuna',
        'Xiphias gladius': 'Swordfish',
        'Istiophorus platypterus': 'Indo-Pacific sailfish',
        'Makaira nigricans': 'Blue marlin',
        'Tetrapturus audax': 'Striped marlin',
    },

    # Cephalopods
    'Cephalopods': {
        'Dosidicus gigas': 'Humboldt squid / Jumbo squid',
        'Loligo opalescens': 'Market squid',
        'Loligo vulgaris': 'Atlantic squid',
        'Octopus vulgaris': 'Common octopus',
        'Octopus dofleini': 'Giant Pacific octopus',
    },

    # Snappers and Groupers
    'Snappers_Groupers': {
        'Lutjanus guttatus': 'Spotted rose snapper',
        'Lutjanus peru': 'Red snapper',
        'Lutjanus argentiventris': 'Yellow snapper',
        'Epinephelus labriformis': 'Grouper',
        'Epinephelus itajara': 'Goliath grouper',
        'Mycteroperca prionura': 'Leopard grouper',
        'Mycteroperca rosacea': 'Rosy grouper',
        'Mycteroperca olfax': 'Spotted grouper',
    },

    # Jacks and Carangids
    'Carangidae': {
        'Caranx caballus': 'Green jack',
        'Caranx hippos': 'Crevalle jack',
        'Caranx lugubris': 'Black jack',
        'Decapterus macarellus': 'Shortfin scad',
        'Decapterus punctatus': 'Round scad',
        'Selar crumenophthalmus': 'Bigeye scad',
        'Trachinotus species': 'Pompano species',
    },

    # Benthic/Demersal invertebrates
    'Crustaceans': {
        'Penaeus vannamei': 'White shrimp',
        'Penaeus stylirostris': 'Blue shrimp',
        'Pandalus borealis': 'Northern shrimp',
        'Callinectes sapidus': 'Blue crab',
        'Chionoecetes opilio': 'Snow crab',
        'Cancer productus': 'Red rock crab',
        'Octopu cyanea': 'Octopus',
    },

    # Reef fish and associated species
    'Reef_Fish': {
        'Thalassoma lucasanum': 'Rainbow wrasse',
        'Halichoeres semicinctus': 'Wrasse',
        'Bodianus diplotaenia': 'Mexican hogfish',
        'Semicossyphus darwini': 'Señorita',
        'Chromis atripectoralis': 'Damselfish',
        'Abudefduf saxatilis': 'Sergeant major',
        'Chaetodon humeralis': 'Black-striped angelfish',
    },

    # Deep-sea species
    'Deep_Sea': {
        'Argyropelecus aculeatus': 'Hatchetfish',
        'Photichthys flagelligerus': 'Hatchetfish',
        'Diretmichthys parini': 'Spinyfin',
        'Poromitra crassiceps': 'Fangtooth fish',
        'Coelorhynchus species': 'Grenadier',
    },

    # Shark and Rays
    'Elasmobranchs': {
        'Squalus acanthias': 'Pacific spiny dogfish',
        'Hexanchus griseus': 'Bluntnose sixgill shark',
        'Lamna nasus': 'Porbeagle shark',
        'Carcharhinus limbatus': 'Blacktip shark',
        'Carcharhinus leucas': 'Bull shark',
        'Prionace glauca': 'Blue shark',
        'Rhinoptera steindachneri': 'Bat ray',
        'Myliobatis californica': 'California eagle ray',
        'Mobula mobular': 'Manta ray',
    },
}

def generate_species_list(output_file: str = 'data/input/goc_species_list.csv'):
    """Generate comprehensive GOC species list CSV file"""

    records = []

    for ecological_group, species_dict in GOC_SPECIES_DATABASE.items():
        for scientific_name, common_name in species_dict.items():
            records.append({
                'scientific_name': scientific_name,
                'common_name': common_name,
                'ecological_group': ecological_group,
            })

    # Create DataFrame
    df = pd.DataFrame(records)

    # Save to CSV
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)

    logger.info(f"Generated GOC species list with {len(df)} species")
    logger.info(f"Ecological groups: {df['ecological_group'].nunique()}")
    logger.info(f"Saved to: {output_file}")

    # Print summary by group
    print("\n" + "="*70)
    print("GULF OF CALIFORNIA SPECIES DATABASE")
    print("="*70)
    for group in sorted(df['ecological_group'].unique()):
        count = len(df[df['ecological_group'] == group])
        print(f"  • {group}: {count} species")
    print(f"\nTotal: {len(df)} species")
    print("="*70 + "\n")

    return df

def main():
    df = generate_species_list()
    print("\nFirst 10 species:")
    print(df.head(10).to_string(index=False))

if __name__ == '__main__':
    main()
