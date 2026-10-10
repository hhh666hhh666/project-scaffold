package ${PACKAGE}.security;

import ${PACKAGE}.common.BusinessException;
import ${PACKAGE}.common.ResultCode;

/**
 * 保存当前登录用户 id，生命周期为一次请求。
 */
public final class UserContext {

    private static final ThreadLocal<Long> CURRENT_USER = new ThreadLocal<>();

    private UserContext() {
    }

    public static void setUserId(Long userId) {
        CURRENT_USER.set(userId);
    }

    public static Long getUserId() {
        return CURRENT_USER.get();
    }

    /**
     * 当前登录用户 id，未登录时抛出未登录异常。
     */
    public static Long requireUserId() {
        Long userId = CURRENT_USER.get();
        if (userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED);
        }
        return userId;
    }

    public static void clear() {
        CURRENT_USER.remove();
    }
}
