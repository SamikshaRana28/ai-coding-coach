# import sys, os
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# from ml.score import calculate_readiness_score
# from ml.predict import predict_weak_topic

# def test_score_range():
#     result = calculate_readiness_score(10,10,10,10,10,10,2.0,0.5)
#     assert 0 <= result["total_score"] <= 100

# def test_score_breakdown_sums():
#     result = calculate_readiness_score(50,50,50,50,50,50,1.5,0.8)
#     breakdown_sum = sum(result["breakdown"].values())
#     assert abs(breakdown_sum - result["total_score"]) < 0.1

# def test_weak_topic_prediction():
#     result = predict_weak_topic(0,10,10,10,10,10,2.0,0.5)
#     assert result["weak_topic"] in ["arrays","graphs","dp","trees","strings","math"]
#     assert 0 <= result["confidence"] <= 1












import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.score import calculate_readiness_score
from ml.predict import predict_weak_topic

def test_score_range():
    result = calculate_readiness_score(10,10,10,10,10,10,2.0,0.5)
    assert 0 <= result["total_score"] <= 100

def test_score_breakdown_sums():
    result = calculate_readiness_score(50,50,50,50,50,50,1.5,0.8)
    breakdown_sum = sum(result["breakdown"].values())
    assert abs(breakdown_sum - result["total_score"]) < 0.1

def test_weak_topic_prediction():
    result = predict_weak_topic(0,10,10,10,10,10,2.0,0.5)
    assert result["weak_topic"] in ["arrays","graphs","dp","trees","strings","math"]
    assert 0 <= result["confidence"] <= 1