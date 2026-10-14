from nablamath import MLP

X = [[-1.0], [0.0], [1.0], [2.0], [3.0]]
y = [-2.0, 1.0, 4.0, 7.0, 10.0]

model = MLP([1, 8, 8, 1])
history = model.train_regression(X, y, lr=0.03, epochs=300)

print("Parâmetros:", model.parameter_count())
print("Loss inicial:", history[0])
print("Loss final:", history[-1])
