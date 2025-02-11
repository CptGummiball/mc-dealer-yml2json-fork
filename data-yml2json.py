#!/usr/bin/env python3

"""
Minecraft Händler-YML zu JSON-Konverter

Autor: VollmondHeuler, CaptainGummiball
Lizenz: CC-BY 4.0

Beschreibung:
Gibt einen JSON Array aus für ein Data-Verzeichnis voller Händlerdaten
"""

import os
import json
import re
import base64
import nbtlib
import tempfile
import traceback
from datetime import datetime
import yaml

global LATEST_FILEMODDATE
LATEST_FILEMODDATE = None

global BEST_OFFERS
BEST_OFFERS = {}

global BEST_DEMANDS
BEST_DEMANDS = {}

global HIDDEN_SHOPS
HIDDEN_SHOPS = []

def clean_minecraft_string(text):
    # Pattern for Minecraft formatting codes
    pattern = re.compile(r"§[0-9a-fklmnor]")
    return re.sub(pattern, "", text)

def read_uuids_from_file(file_path):
    uuid_list = []

    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            try:
                data = json.load(file)
                if isinstance(data, list):
                    uuid_list = [
                        uuid
                        for uuid in data
                        if isinstance(uuid, str) and len(uuid) == 36
                    ]
            except json.JSONDecodeError:
                pass

    return uuid_list

def decode_nbt_data(base64_string):
    decoded_bytes = base64.b64decode(base64_string)
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(decoded_bytes)
        temp_file.seek(0)
        nbt_data = nbtlib.load(temp_file.name)
    
    return nbt_data

def read_yaml_files(directory):
    global LATEST_FILEMODDATE
    global HIDDEN_SHOPS
    data_dict = {}
    for filename in os.listdir(directory):
        if filename.endswith(".yml"):
            base_filename = os.path.splitext(os.path.basename(filename))[0]
            if base_filename in HIDDEN_SHOPS:
                continue
            with open(os.path.join(directory, filename), "r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
                uuid = data.get("ownerUUID")
                if not uuid:
                    uuid = base_filename
                data["shop_uuid"] = base_filename
                data_dict[base_filename] = data
                file_stat = os.stat(os.path.join(directory, filename))
                modified_time = file_stat.st_mtime
                if LATEST_FILEMODDATE is None or modified_time > LATEST_FILEMODDATE:
                    LATEST_FILEMODDATE = modified_time
                    # print(data)
    return data_dict

# Specify the directory with the YAML files
DIRECTORY_PATH = "data/"
HIDDEN_SHOPS = read_uuids_from_file("hidden_shops.json")
result_dict = read_yaml_files(DIRECTORY_PATH)

if __name__ == "__main__":
    try:
        player_shops = {
            "meta": {"latestfilemoddate": None, "latestfilemoddate_formatted": None},
            "shops": [],
        }
        for shop in result_dict:
            if result_dict[shop]["shop_uuid"] in HIDDEN_SHOPS:
                continue
            player_shop = {}

            # Meta data of the shop
            player_shop["shop_uuid"] = result_dict[shop]["shop_uuid"]
            player_shop["shop_type"] = result_dict[shop]["type"]
            if "ownerUUID" in result_dict[shop]:
                player_shop["owner_uuid"] = result_dict[shop]["ownerUUID"]
            if player_shop["shop_type"] == "ADMIN":
                player_shop["owner_name"] = "ADMIN"

            if "ownerName" in result_dict[shop]:
                player_shop["owner_name"] = result_dict[shop]["ownerName"]

            player_shop["shop_name"] = clean_minecraft_string(
                result_dict[shop]["entity"]["name"]
            )
            player_shop["shop_name"] = re.sub(
                r"\[.*?\]", "", player_shop["shop_name"]
            ).strip()
            player_shop["npc_profession"] = result_dict[shop]["entity"]["profession"]
            player_shop["location"] = {
                "world": result_dict[shop]["entity"]["location"]["world"],
                "x": result_dict[shop]["entity"]["location"]["x"],
                "y": result_dict[shop]["entity"]["location"]["y"],
                "z": result_dict[shop]["entity"]["location"]["z"],
            }

            player_offers = {}
            player_demands = {}

            if "items_for_sale" in result_dict[shop]:
                for offer in result_dict[shop]["items_for_sale"]:
                    offer_data = result_dict[shop]["items_for_sale"][offer]
                    # Offers of the dealer
                    if offer_data["mode"] == "SELL":
                        player_offer = {}
                        player_offer["own_name"] = None
                        item_type = offer_data["item"]["type"]
                        item_index = item_type

                        if item_type == "POTION":
                            if "potion-type" in offer_data["item"]["meta"]:
                                item_type = offer_data["item"]["meta"]["potion-type"]
                                item_index = item_type
                            else:
                                own_name = offer_data["item"]["meta"]["display-name"]
                                item_index = own_name

                        elif item_type == "ENCHANTED_BOOK":
                            item_type = (
                                "ENCHANTED_BOOK_"
                                + list(offer_data["item"]["meta"]["stored-enchants"])[0]
                            )
                            item_index = item_type

                        if (
                            "meta" in offer_data["item"]
                            and "display-name" in offer_data["item"]["meta"]
                        ):
                            json_displayname = json.loads(
                                offer_data["item"]["meta"]["display-name"]
                            )
                            if ("extra" in json_displayname
                                and len(json_displayname["extra"]) > 0
                                and "text" in json_displayname["extra"][0]):
                                player_offer["own_name"] = json_displayname["extra"][0]["text"]
                                item_index = player_offer["own_name"]
                            elif ("extra" in json_displayname
                                and len(json_displayname["extra"]) > 0):
                                player_offer["own_name"] = json_displayname["extra"][0]
                                item_index = player_offer["own_name"]
                            elif "translate" in json_displayname:
                                player_offer["own_name"] = json_displayname["translate"]
                                item_index = player_offer["own_name"]

                        player_offer["item"] = item_type
                        player_offer["item"] = item_type.replace("minecraft:", "", 1)
                        player_offer["amount"] = offer_data["amount"]
                        player_offer["exchange_item"] = "money"

                        if isinstance(offer_data["price"], (int, float)):
                            player_offer["price"] = offer_data["price"]
                        elif "type" in offer_data["price"]:
                            player_offer["exchange_item"] = offer_data["price"][
                                "type"
                            ].replace("minecraft:", "", 1)
                            player_offer["price"] = 1
                            if "amount" in offer_data["price"]:
                                player_offer["price"] = offer_data["price"]["amount"]

                        player_offer["price_discount"] = 0
                        if (
                            "discount" in offer_data
                            and "amount" in offer_data["discount"]
                        ):
                            player_offer["price_discount"] = offer_data["discount"][
                                "amount"
                            ]

                        player_offer["unit_price"] = (
                            player_offer["price"] / offer_data["amount"]
                        )
                        player_offer["stock"] = 0
                        player_offer["is_best_price"] = None

                        if "meta" in offer_data["item"]:
                            if "enchants" in offer_data["item"]["meta"]:
                                player_offer["enchants"] = []
                                for enchantment in offer_data["item"]["meta"]["enchants"]:
                                    player_offer["enchants"].append(
                                        {
                                            "name": enchantment,
                                            "level": offer_data["item"]["meta"]["enchants"][
                                                enchantment
                                            ],
                                        }
                                    )
                            if "ItemFlags" in offer_data["item"]["meta"] and "HIDE_ARMOR_TRIM" in offer_data["item"]["meta"]["ItemFlags"] and "internal" in offer_data["item"]["meta"]:
                                internal_data = decode_nbt_data(offer_data["item"]["meta"]["internal"])

                                if ("BlockEntityTag" in internal_data 
                                    and "Items" in internal_data["BlockEntityTag"] 
                                    and len(internal_data["BlockEntityTag"]["Items"]) > 0
                                    and "tag" in internal_data["BlockEntityTag"]["Items"][0]
                                    and "simpledrawer" in internal_data["BlockEntityTag"]["Items"][0]["tag"]
                                    ):

                                    simpledrawer_data = internal_data["BlockEntityTag"]["Items"][0]["tag"]["simpledrawer"]
                                    # cleanups
                                    if("maxCount" in simpledrawer_data):
                                        del(simpledrawer_data["maxCount"])
                                    if("version" in simpledrawer_data):
                                        del(simpledrawer_data["version"])
                                    if("globalCount" in simpledrawer_data):
                                        del(simpledrawer_data["globalCount"])
                                    if("wood_type" in simpledrawer_data):
                                        if simpledrawer_data["wood_type"].startswith("simpledrawer:"):
                                            simpledrawer_data["wood_type"] = simpledrawer_data["wood_type"][13:]

                                    player_offer["simpledrawer"] = simpledrawer_data
                                    


                        if (
                            player_shop["shop_type"] == "ADMIN"
                            and player_offer["exchange_item"] == "money"
                        ):
                            discounted_unitprice = player_offer["unit_price"] * (
                                1 - (player_offer["price_discount"] / 100)
                            )
                            if (
                                player_offer["item"] not in BEST_OFFERS
                                or BEST_OFFERS[player_offer["item"]]
                                > discounted_unitprice
                            ):
                                BEST_OFFERS[player_offer["item"]] = discounted_unitprice

                        player_offers[item_index] = player_offer

                    # Demands of the dealer
                    elif offer_data["mode"] == "BUY":
                        player_demand = {}

                        item_type = offer_data["item"]["type"]
                        player_demand["item"] = item_type.replace("minecraft:", "", 1)
                        player_demand["own_name"] = None
                        player_demand["amount"] = offer_data["amount"]
                        player_demand["exchange_item"] = "money"

                        if isinstance(offer_data["buy_price"], (int, float)):
                            player_demand["price"] = offer_data["buy_price"]
                        elif "type" in offer_data["price"]:
                            player_demand["exchange_item"] = offer_data["price"][
                                "type"
                            ].replace("minecraft:", "", 1)
                            player_demand["price"] = offer_data["price"]["amount"]

                        player_demand["unit_price"] = (
                            player_demand["price"] / offer_data["amount"]
                        )
                        player_demand["buy_limit"] = offer_data["buy_limit"]
                        player_demand["is_best_price"] = None

                        item_index = item_type
                        player_demands[item_index] = player_demand

                        if (
                            player_demand["exchange_item"] == "money"
                            and player_demand["item"] not in BEST_DEMANDS
                            or BEST_DEMANDS[player_demand["item"]]
                            < player_demand["unit_price"]
                        ):
                            BEST_DEMANDS[player_demand["item"]] = player_demand[
                                "unit_price"
                            ]

            # stock levels
            player_stocks = {}
            if "storage" in result_dict[shop]:
                for stock in result_dict[shop]["storage"]:
                    item_type = stock["type"]
                    item_index = stock["type"]

                    if item_type == "POTION":
                        if "potion-type" in stock["meta"]:
                            item_type = stock["meta"]["potion-type"]
                            item_index = item_type
                        else:
                            own_name = stock["item"]["display-name"]
                            item_index = own_name

                    elif item_type == "ENCHANTED_BOOK":
                        item_type = (
                            "ENCHANTED_BOOK_"
                            + list(stock["meta"]["stored-enchants"])[0]
                        )
                        item_index = item_type

                    if "meta" in stock and "display-name" in stock["meta"]:
                        json_displayname = json.loads(stock["meta"]["display-name"])
                        if ("extra" in json_displayname
                             and len(json_displayname["extra"]) > 0
                             and "text" in json_displayname["extra"][0]):
                            item_index = json_displayname["extra"][0]["text"]
                        elif ("extra" in json_displayname
                            and len(json_displayname["extra"]) > 0):
                            item_index = json_displayname["extra"][0]
                        elif "translate" in json_displayname:
                            item_index = json_displayname["translate"]

                    myamount = 1
                    if "amount" in stock:
                        myamount = stock["amount"]

                    if item_index not in player_stocks:
                        player_stocks[item_index] = myamount
                    else:
                        player_stocks[item_index] += myamount

                # Transfer stock levels to offers and demands
                for stock_key in player_stocks:
                    if stock_key in player_offers:
                        best_offers_key = player_offers[stock_key]["item"]
                        player_offers[stock_key]["stock"] = player_stocks[stock_key]
                        discounted_unitprice = player_offers[stock_key][
                            "unit_price"
                        ] * (1 - (player_offers[stock_key]["price_discount"] / 100))

                        if (
                            player_offers[stock_key]["exchange_item"] == "money"
                            and player_stocks[stock_key] > 0
                            and best_offers_key not in BEST_OFFERS
                            or BEST_OFFERS[best_offers_key] > discounted_unitprice
                        ):
                            BEST_OFFERS[best_offers_key] = discounted_unitprice
                    if (
                        stock_key in player_demands
                        and "buy_limit" in player_demands[stock_key]
                        and player_shop["shop_type"] == "PLAYER"
                    ):
                        player_demands[stock_key]["buy_limit"] -= player_stocks[
                            stock_key
                        ]
                        if player_demands[stock_key]["buy_limit"] < 0:
                            player_demands[stock_key]["buy_limit"] = 0

            player_shop["offers"] = player_offers
            player_shop["demands"] = player_demands
            player_shops["shops"].append(player_shop)
            player_shops["meta"]["latestfilemoddate"] = LATEST_FILEMODDATE
            player_shops["meta"][
                "latestfilemoddate_formatted"
            ] = datetime.fromtimestamp(LATEST_FILEMODDATE).strftime("%Y-%m-%d %H:%M:%S")

        # determine best-prices
        for shop in player_shops["shops"]:
            for offer_key in shop["offers"]:
                discounted_unitprice = shop["offers"][offer_key]["unit_price"] * (
                    1 - (shop["offers"][offer_key]["price_discount"] / 100)
                )
                best_offers_key = shop["offers"][offer_key]["item"]
                if (
                    (
                        shop["shop_type"] == "ADMIN"
                        or shop["offers"][offer_key]["stock"] > 0
                    )
                    and best_offers_key in BEST_OFFERS
                    and discounted_unitprice == BEST_OFFERS[best_offers_key]
                ):
                    shop["offers"][offer_key]["is_best_price"] = True
                else:
                    shop["offers"][offer_key]["is_best_price"] = False

            for demand_key in shop["demands"]:
                best_demands_key = shop["demands"][demand_key]["item"]
                if (
                    shop["demands"][best_demands_key]["unit_price"]
                    == BEST_DEMANDS[best_demands_key]
                ):
                    shop["demands"][best_demands_key]["is_best_price"] = True
                else:
                    shop["demands"][best_demands_key]["is_best_price"] = False

        # Data output as JSON file
        with open("web/output.json", "w") as outfile:
            outfile.write(json.dumps(player_shops))

        # Error Handling (Error output in the event of an error)
        pass
    except Exception as e:
        traceback.print_exc()
