import os
import json
import boto3
from flask import Flask, request, jsonify

dynamodb = boto3.resource('dynamodb')
wagertable = dynamodb.Table('wagers')
wagerboard = dynamodb.Table('wagerboard')

app = Flask(__name__)
@app.route('/', methods=['POST'])
def lambda_handler():
	raw = request.form.get('payload')
	content = json.loads(raw)
	print("CONTENT IS")
	print(content)
	callback_id = content['callback_id']
	username = content['user']['name']
	userid = content['user']['id']
	bettor = f"<@{userid}|{username}>"
	options = []

	rows = wagertable.scan(
		ProjectionExpression="bettors, thebet, thestakes, #d, resolved, #u, title",
		ExpressionAttributeNames= {'#d':'date', '#u':'uuid'},
		)

	for entry in rows['Items']:
		if entry['resolved'] == True:
			pass
		else:
			if bettor in entry['bettors']:
				bettor1 = entry['bettors'][0]
				bettor2 = entry['bettors'][1]
				thebet = entry['thebet']
				betdate = entry['date']
				uuid = entry['uuid']
				title = entry['title']
				print(uuid)
				if bettor1 == bettor:
					finalbettor = bettor2
				else:
					finalbettor = bettor1
				jsonstub = [{"label": f"{title} (w/{finalbettor})","value": uuid}]
				options.append(jsonstub[0])

	returnvalue = {'options': options}
	print(f'Return Value Is {returnvalue}')
	return jsonify(returnvalue)