"""
Sirf TESTING ke liye: question bank ke tests sahi hain ya nahi, ye verify karta hai.
Ye file kabhi LLM ko mat dikhana (answer leak ho jayega).
"""

REFS = {
    "two_sum": ("two_sum", """
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        if target - x in seen:
            return [seen[target - x], i]
        seen[x] = i
    return []
""", [[[2, 7, 11, 15], 9], [[3, 2, 4], 6], [[3, 3], 6], [[1, 5, 9, 14], 23]]),

    "valid_parentheses": ("is_valid", """
def is_valid(s):
    pairs = {')': '(', ']': '[', '}': '{'}
    st = []
    for ch in s:
        if ch in pairs:
            if not st or st.pop() != pairs[ch]:
                return False
        else:
            st.append(ch)
    return not st
""", [["()"], ["()[]{}"], ["(]"], ["([)]"], ["{[]}"], [""], ["(("]]),

    "best_time_to_buy_sell": ("max_profit", """
def max_profit(prices):
    best, low = 0, float('inf')
    for p in prices:
        low = min(low, p)
        best = max(best, p - low)
    return best
""", [[[7, 1, 5, 3, 6, 4]], [[7, 6, 4, 3, 1]], [[1]], [[2, 4, 1]], [[]]]),

    "longest_unique_substring": ("length_of_longest_substring", """
def length_of_longest_substring(s):
    last, start, best = {}, 0, 0
    for i, ch in enumerate(s):
        if ch in last and last[ch] >= start:
            start = last[ch] + 1
        last[ch] = i
        best = max(best, i - start + 1)
    return best
""", [["abcabcbb"], ["bbbbb"], ["pwwkew"], [""], ["abba"], ["dvdf"]]),

    "max_subarray": ("max_subarray", """
def max_subarray(nums):
    best = cur = nums[0]
    for x in nums[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return best
""", [[[-2, 1, -3, 4, -1, 2, 1, -5, 4]], [[1]], [[5, 4, -1, 7, 8]], [[-3, -2, -5]]]),

    "binary_search": ("search", """
def search(nums, target):
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""", [[[-1, 0, 3, 5, 9, 12], 9], [[-1, 0, 3, 5, 9, 12], 2], [[5], 5], [[], 1], [[1, 2, 3, 4], 4]]),

    "climbing_stairs": ("climb_stairs", """
def climb_stairs(n):
    a, b = 1, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b
""", [[1], [2], [3], [5], [10], [30]]),

    "coin_change": ("coin_change", """
def coin_change(coins, amount):
    INF = amount + 1
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a:
                dp[a] = min(dp[a], dp[a - c] + 1)
    return dp[amount] if dp[amount] != INF else -1
""", [[[1, 2, 5], 11], [[2], 3], [[1], 0], [[186, 419, 83, 408], 6249], [[3, 7], 5]]),

    "contains_duplicate": ("contains_duplicate", """
def contains_duplicate(nums):
    return len(set(nums)) != len(nums)
""", [[[1, 2, 3, 1]], [[1, 2, 3, 4]], [[]], [[1, 1, 1, 3, 3, 4, 3, 2, 4, 2]]]),

    "product_except_self": ("product_except_self", """
def product_except_self(nums):
    n = len(nums)
    out = [1] * n
    left = 1
    for i in range(n):
        out[i] = left
        left *= nums[i]
    right = 1
    for i in range(n - 1, -1, -1):
        out[i] *= right
        right *= nums[i]
    return out
""", [[[1, 2, 3, 4]], [[-1, 1, 0, -3, 3]], [[2, 3]], [[0, 0]]]),
}
