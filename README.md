# OptStrat

Python-based app to find options contracts that adhere to a configured strategy using Poylgon.io data.

## SUPPORTED STRATEGIES

### PRE-EARNINGS LONG STRADDLE

* On a high-level this means to buy both call/put options 7-30 days before earnings and to sell the day or the hours leading to the earnings to capitalize on the IV expansion and avoid IV crush.
    * Low theta to avoid time decay. 
    * High vega to maximize IV swings.

* Give input strategy as 'longStraddleIV' to use.

## HOW TO RUN

Ensure the SECRETS_FILE_PATH environment variable is set to the .yaml file containing your polygon api key with the field POLYGON_API_KEY.

Use findAll to find all the options that satisfy this strategy.
```python
python3 -m app.main findAll longStraddleIV
```

Use findOne with a ticker to find the options that satisfy this strategy for the exact given ticker.
```python
python3 -m app.main findOne longStraddleIV AAPL
```

## NEXT STEPS

* The app is abstracted such that any different strategy can be easily added. Will explore adding more strategies in the future.
